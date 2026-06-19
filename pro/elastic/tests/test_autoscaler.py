import base64
import contextlib
import io
import types
import unittest
from pathlib import Path


TERRAFORM_FILE = Path(__file__).resolve().parents[1] / "tf-do-openvidu-elastic.tf"


def load_autoscaler():
    terraform = TERRAFORM_FILE.read_text()
    source = terraform.split("autoscaler_function_code = <<-PYEOF\n", 1)[1].split(
        "\nPYEOF", 1
    )[0]
    replacements = {
        "${var.autoscalerToken}": "test-token",
        "${digitalocean_tag.media_node_tag.name}": "media",
        "${digitalocean_tag.draining_tag.name}": "draining",
        "${var.region}": "test-region",
        "${var.mediaNodeInstanceType}": "test-size",
        "${digitalocean_vpc.openvidu_vpc.id}": "test-vpc",
        "${digitalocean_ssh_key.openvidu_ssh_key_do.id}": "123",
        "${var.stackName}": "test-stack",
        "${var.minNumberOfMediaNodes}": "1",
        "${var.maxNumberOfMediaNodes}": "4",
        "${var.scaleTargetCPU}": "50",
        "${base64encode(local.user_data_media)}": base64.b64encode(b"test").decode(),
    }
    for placeholder, value in replacements.items():
        source = source.replace(placeholder, value)
    if "${" in source:
        raise AssertionError("Autoscaler test loader is missing a Terraform substitution")

    module = types.ModuleType("courseultra_autoscaler")
    exec(compile(source, str(TERRAFORM_FILE), "exec"), module.__dict__)
    return module


def node(node_id, name, tags=None):
    return {
        "id": node_id,
        "name": name,
        "status": "active",
        "region": {"slug": "test-region"},
        "created_at": "2026-06-18T00:00:00Z",
        "tags": ["media"] if tags is None else tags,
    }


def metrics(**overrides):
    counters = {
        "idle": (0, 90),
        "iowait": (0, 0),
        "irq": (0, 0),
        "nice": (0, 0),
        "softirq": (0, 0),
        "steal": (0, 0),
        "system": (0, 5),
        "user": (0, 5),
    }
    counters.update(overrides)
    return {
        "data": {
            "result": [
                {
                    "metric": {"mode": mode},
                    "values": [[1, values[0]], [2, values[1]]],
                }
                for mode, values in counters.items()
            ]
        }
    }


class AutoscalerSafetyTest(unittest.TestCase):
    def setUp(self):
        self.autoscaler = load_autoscaler()

    def invoke(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.autoscaler.main({})["body"]

    def test_inventory_failure_holds_capacity(self):
        calls = []

        def api(method, path, body=None):
            calls.append((method, path))
            return None

        self.autoscaler.apicall = api
        result = self.invoke()

        self.assertEqual("hold", result["action"])
        self.assertIn("inventory", result["error"])
        self.assertEqual([("GET", "/droplets?tag_name=media&per_page=200")], calls)

    def test_malformed_tag_inventory_holds_without_scaling(self):
        calls = []
        malformed_node = node(1, "one")
        del malformed_node["tags"]

        def api(method, path, body=None):
            calls.append((method, path))
            if path.startswith("/droplets?"):
                return {"droplets": [malformed_node]}
            raise AssertionError(f"Unexpected API call: {method} {path}")

        self.autoscaler.apicall = api
        result = self.invoke()

        self.assertEqual("hold", result["action"])
        self.assertIn("tag metadata", result["error"])
        self.assertEqual([("GET", "/droplets?tag_name=media&per_page=200")], calls)

    def test_dual_tagged_node_does_not_mask_minimum_capacity(self):
        calls = []
        draining_node = node(1, "draining", ["media", "draining"])

        def api(method, path, body=None):
            calls.append((method, path))
            if path.startswith("/droplets?"):
                return {"droplets": [draining_node]}
            if method == "POST" and path == "/droplets":
                return {"droplet": node(2, "replacement")}
            raise AssertionError(f"Unexpected API call: {method} {path}")

        self.autoscaler.apicall = api
        result = self.invoke()

        self.assertEqual("scale-out-min", result["action"])
        self.assertEqual(0, result["nodes"])
        self.assertEqual(1, result["draining_nodes"])
        self.assertTrue(result["created"])
        self.assertEqual(
            [
                ("GET", "/droplets?tag_name=media&per_page=200"),
                ("POST", "/droplets"),
            ],
            calls,
        )

    def test_incomplete_metrics_do_not_add_or_drain_nodes(self):
        calls = []
        nodes = [node(1, "one"), node(2, "two")]

        def api(method, path, body=None):
            calls.append((method, path))
            if path.startswith("/droplets?"):
                return {"droplets": nodes}
            return None

        self.autoscaler.apicall = api
        result = self.invoke()

        self.assertEqual("hold", result["action"])
        self.assertIn("0/2", result["error"])
        self.assertTrue(all(method == "GET" for method, _ in calls))

    def test_zero_counter_values_are_valid_samples(self):
        self.autoscaler.apicall = lambda method, path, body=None: metrics(
            idle=(0, 70), iowait=(0, 0), system=(0, 20), user=(0, 10)
        )

        with contextlib.redirect_stdout(io.StringIO()):
            usage = self.autoscaler.cpu(1, "one")

        self.assertAlmostEqual(30.0, usage)

    def test_all_provider_cpu_modes_contribute_to_utilization(self):
        self.autoscaler.apicall = lambda method, path, body=None: metrics(
            idle=(0, 70),
            iowait=(0, 10),
            irq=(0, 2),
            nice=(0, 2),
            softirq=(0, 3),
            steal=(0, 3),
            system=(0, 5),
            user=(0, 5),
        )

        with contextlib.redirect_stdout(io.StringIO()):
            usage = self.autoscaler.cpu(1, "one")

        self.assertAlmostEqual(20.0, usage)

    def test_changed_provider_mode_set_holds_scaling(self):
        response = metrics()
        response["data"]["result"] = [
            item for item in response["data"]["result"] if item["metric"]["mode"] != "nice"
        ]
        self.autoscaler.apicall = lambda method, path, body=None: response

        with contextlib.redirect_stdout(io.StringIO()):
            usage = self.autoscaler.cpu(1, "one")

        self.assertIsNone(usage)

    def test_counter_reset_is_not_treated_as_low_cpu(self):
        self.autoscaler.apicall = lambda method, path, body=None: metrics(
            idle=(100, 5), system=(20, 25), user=(10, 15)
        )

        with contextlib.redirect_stdout(io.StringIO()):
            usage = self.autoscaler.cpu(1, "one")

        self.assertIsNone(usage)

    def test_failed_draining_tag_does_not_remove_active_tag(self):
        calls = []
        nodes = [node(1, "one"), node(2, "two")]

        def api(method, path, body=None):
            calls.append((method, path))
            if path.startswith("/droplets?"):
                return {"droplets": nodes}
            if path.startswith("/monitoring/"):
                return metrics()
            if method == "POST" and path == "/tags/draining/resources":
                return None
            raise AssertionError(f"Unexpected API call: {method} {path}")

        self.autoscaler.apicall = api
        result = self.invoke()

        self.assertEqual("hold", result["action"])
        self.assertIn("Could not mark", result["error"])
        self.assertFalse(any(method == "DELETE" for method, _ in calls))

    def test_drain_tag_precedes_active_tag_removal(self):
        mutations = []
        nodes = [node(1, "one"), node(2, "two")]

        def api(method, path, body=None):
            if path.startswith("/droplets?"):
                return {"droplets": nodes}
            if path.startswith("/monitoring/"):
                return metrics()
            mutations.append((method, path))
            return {}

        self.autoscaler.apicall = api
        result = self.invoke()

        self.assertEqual("scale-in", result["action"])
        self.assertEqual(
            [
                ("POST", "/tags/draining/resources"),
                ("DELETE", "/tags/media/resources"),
            ],
            mutations,
        )

    def test_active_tag_failure_leaves_confirmed_drain_in_progress(self):
        mutations = []
        nodes = [node(1, "one"), node(2, "two")]

        def api(method, path, body=None):
            if path.startswith("/droplets?"):
                return {"droplets": nodes}
            if path.startswith("/monitoring/"):
                return metrics()
            mutations.append((method, path))
            return {} if method == "POST" else None

        self.autoscaler.apicall = api
        result = self.invoke()

        self.assertEqual("scale-in", result["action"])
        self.assertIn("still has its active tag", result["warning"])
        self.assertEqual(
            [
                ("POST", "/tags/draining/resources"),
                ("DELETE", "/tags/media/resources"),
            ],
            mutations,
        )

    def test_active_tag_failure_cannot_start_another_drain_next_run(self):
        mutations = []
        nodes = [node(1, "one"), node(2, "two"), node(3, "three")]

        def api(method, path, body=None):
            if path.startswith("/droplets?"):
                return {"droplets": nodes}
            if path.startswith("/monitoring/"):
                return metrics()
            mutations.append((method, path))
            if method == "POST" and path == "/tags/draining/resources":
                resource_id = int(body["resources"][0]["resource_id"])
                selected = next(item for item in nodes if item["id"] == resource_id)
                if "draining" not in selected["tags"]:
                    selected["tags"].append("draining")
                return {}
            if method == "DELETE" and path == "/tags/media/resources":
                return None
            raise AssertionError(f"Unexpected API call: {method} {path}")

        self.autoscaler.apicall = api

        first_result = self.invoke()
        second_result = self.invoke()

        self.assertEqual("scale-in", first_result["action"])
        self.assertIn("still has its active tag", first_result["warning"])
        self.assertEqual("hold", second_result["action"])
        self.assertEqual(2, second_result["nodes"])
        self.assertEqual(1, second_result["draining_nodes"])
        self.assertIn("Scale-in deferred", second_result["warning"])
        self.assertEqual(
            [
                ("POST", "/tags/draining/resources"),
                ("DELETE", "/tags/media/resources"),
            ],
            mutations,
        )


if __name__ == "__main__":
    unittest.main()
