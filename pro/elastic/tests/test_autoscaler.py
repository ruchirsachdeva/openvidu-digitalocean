import base64
import contextlib
import io
import json
import types
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch


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
        "${var.automaticScaleInEnabled}": "false",
        "${var.capacityReservationsEnabled}": "false",
        "${var.capacityProfileFingerprint}": "qualified-do-ams3-v1",
        "${base64encode(var.capacityBackendUrl)}": base64.b64encode(b"https://backend.example.test").decode(),
        "${base64encode(var.capacityBackendToken)}": base64.b64encode(b"test-capacity-credential").decode(),
        "${base64encode(local.user_data_media_transport)}": base64.b64encode(b"test").decode(),
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
        "size_slug": "test-size",
        "vpc_uuid": "test-vpc",
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


class AutoscalerReadResilienceTest(unittest.TestCase):
    def setUp(self):
        self.scaler = load_autoscaler()
        self.now = 0.0
        for target, name, value in ((self.scaler.time, "monotonic", lambda: self.now),
                                   (self.scaler.time, "sleep", self.advance),
                                   (self.scaler.random, "uniform", lambda low, high: low)):
            helper = patch.object(target, name, value)
            self.addCleanup(helper.stop)
            helper.start()

    def advance(self, seconds):
        self.now += seconds

    def response(self, value):
        response = types.SimpleNamespace(status=200, read=lambda: json.dumps(value).encode())
        return contextlib.nullcontext(response)

    def http_error(self, code):
        return urllib.error.HTTPError(self.scaler.API + "/droplets", code, "synthetic", {}, io.BytesIO(b"unavailable"))

    def invoke(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.scaler.main({})["body"]

    def test_get_timeout_and_522_retry_success_with_short_budget(self):
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=[
                TimeoutError("timed out"), self.http_error(522), self.response({"droplets": []})]) as opener:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual({"droplets": []}, self.scaler.apicall("GET", "/droplets"))
        self.assertEqual(3, opener.call_count)
        self.assertTrue(all(0 < call.kwargs["timeout"] <= 4 for call in opener.call_args_list))
        self.assertGreater(self.now, 0)
        self.assertLess(self.now, 12)

    def test_429_and_wrapped_transport_timeout_retry_but_not_error_body_reads(self):
        throttled = self.http_error(429)
        throttled.read = Mock(side_effect=TimeoutError("diagnostic body unavailable"))
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=[
                throttled, urllib.error.URLError(TimeoutError()), self.response({"droplets": []})]) as opener:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual({"droplets": []}, self.scaler.apicall("GET", "/droplets"))
        self.assertEqual(3, opener.call_count)
        throttled.read.assert_not_called()

    def test_only_transient_do_get_reads_retry_and_mutations_stay_single_attempt(self):
        for method, path, failure in (("GET", "/droplets", self.http_error(403)),
                ("GET", "/droplets", urllib.error.URLError("permanent resolution failure")),
                ("GET", "https://other.example.test/read", TimeoutError()),
                ("POST", "/droplets", self.http_error(522)),
                ("POST", "/tags/draining/resources", TimeoutError()),
                ("DELETE", "/tags/media/resources", self.http_error(429))):
            with self.subTest(method=method, path=path):
                with patch.object(self.scaler.urllib.request, "urlopen", side_effect=failure) as opener:
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertIsNone(self.scaler.apicall(method, path))
                self.assertEqual(1, opener.call_count)

    def test_persistent_inventory_timeout_holds_without_claim_or_create(self):
        self.scaler.CAPACITY_ENABLED = True
        authority = Mock(return_value={})
        self.scaler.capacity_request = authority
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=TimeoutError()) as opener:
            for _ in range(2):
                result = self.invoke()
                self.assertTrue(result["readiness_wait"])
                self.assertNotIn("error", result)
        self.assertEqual(6, opener.call_count)
        self.assertEqual(["READINESS_UNAVAILABLE"] * 2, [call.args[1]["code"] for call in authority.call_args_list])
        self.assertTrue(all(call.args[0] == "alert" for call in authority.call_args_list))
        self.assertTrue(all(call.args[0].method == "GET" for call in opener.call_args_list))

    def test_permanent_403_is_a_known_pre_dispatch_hold_without_retry(self):
        self.scaler.CAPACITY_ENABLED = True
        authority = Mock(return_value={})
        self.scaler.capacity_request = authority
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=self.http_error(403)) as opener:
            result = self.invoke()
        self.assertEqual(1, opener.call_count)
        self.assertTrue(result["readiness_wait"])
        self.assertEqual(["READINESS_UNAVAILABLE"], [call.args[1]["code"] for call in authority.call_args_list])

    def test_account_read_failure_holds_before_authoritative_claim(self):
        self.scaler.CAPACITY_ENABLED = True
        self.scaler.MAX_NODES = 0
        authority = Mock(return_value={})
        self.scaler.capacity_request = authority
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=[
                self.response({"droplets": [node(1, "one")]}), self.response({"droplets": []}),
                TimeoutError(), self.http_error(522), TimeoutError()]) as opener:
            result = self.invoke()
        self.assertEqual(5, opener.call_count)
        self.assertTrue(result["readiness_wait"])
        self.assertNotIn("error", result)
        self.assertEqual(["READINESS_UNAVAILABLE"], [call.args[1]["code"] for call in authority.call_args_list])

    def test_shared_deadline_stops_reads_and_reserves_single_attempt_alert_delivery(self):
        self.scaler._DEADLINE = 30.0
        calls = []
        def read(request, timeout):
            calls.append(timeout)
            self.advance(timeout)
            return self.response({"droplets": []})
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=read):
            with contextlib.redirect_stdout(io.StringIO()):
                for _ in range(10):
                    self.scaler.apicall("GET", "/droplets")
        self.assertEqual([4, 4, 2], calls)
        self.assertEqual(10, self.now)
        response = types.SimpleNamespace(read=lambda limit: b"{}")
        def alert(request, timeout):
            self.advance(timeout)
            return contextlib.nullcontext(response)
        opener = Mock()
        opener.open.side_effect = alert
        with patch.object(self.scaler.urllib.request, "build_opener", return_value=opener):
            self.scaler.capacity_request("alert", {})
            self.scaler.capacity_request("alert", {})
            with self.assertRaises(RuntimeError):
                self.scaler.capacity_request("alert", {})
        self.assertEqual(2, opener.open.call_count)
        self.assertEqual(30, self.now)

    def test_budget_hold_does_not_consume_a_dispatch_claim(self):
        self.scaler.CAPACITY_ENABLED = True
        self.scaler.list_nodes = lambda *args: []
        def slow_validation(allocated, result):
            self.advance(90)
            return 4
        self.scaler.account_fleet_limit = slow_validation
        authority = Mock(return_value={})
        self.scaler.capacity_request = authority
        result = self.invoke()
        self.assertTrue(result["readiness_wait"])
        self.assertEqual(["alert"], [call.args[0] for call in authority.call_args_list])

    def test_cloud_create_uses_remaining_global_budget_without_replay(self):
        self.scaler._DEADLINE = 35.0
        def timeout(request, timeout):
            self.advance(timeout)
            raise TimeoutError("unknown creation")
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=timeout) as opener:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertIsNone(self.scaler.apicall("POST", "/droplets", {"user_data": "not-logged"}))
        self.assertEqual(1, opener.call_count)
        self.assertEqual(15, opener.call_args.kwargs["timeout"])
        self.assertEqual(20, self.scaler.time_left())
        self.assertNotIn("not-logged", "\n".join(self.scaler._LOGS))

    def test_known_zero_headroom_holds_without_claim_or_provisioning_failure(self):
        self.scaler.CAPACITY_ENABLED = True
        self.scaler.MAX_NODES = 0
        signals = []
        def authority(path, payload):
            self.assertEqual("alert", path)
            signals.append(payload["code"])
            return {}
        self.scaler.capacity_request = authority
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=[
                self.response({"droplets": []}), self.response({"droplets": []}),
                self.response({"account": {"droplet_limit": 2}}), self.response({"meta": {"total": 2}})]) as opener:
            result = self.invoke()
        self.assertEqual(4, opener.call_count)
        self.assertTrue(result["waiting_for_capacity"])
        self.assertNotIn("error", result)
        self.assertEqual({"ACCOUNT_DROPLET_QUOTA_PRESSURE", "CAPACITY_WAITING"}, set(signals))

    def test_next_healthy_warm_activation_verifies_same_family_before_recovery(self):
        self.scaler.CAPACITY_ENABLED = True
        signals = []
        def authority(path, payload):
            if path == "alert":
                signals.append(payload["code"])
                return {}
            return {"createAllowed": False, "nodeType": "test-size", "intentId": None}
        self.scaler.capacity_request = authority
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=TimeoutError()):
            first = self.invoke()
        self.advance(120)
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=[
                self.response({"droplets": [node(1, "one")]}), self.response({"droplets": []})]):
            second = self.invoke()
        self.assertTrue(first["readiness_wait"])
        self.assertTrue(second["readiness_verified"])
        self.assertNotIn("readiness_wait", second)
        self.assertEqual(["READINESS_UNAVAILABLE", "READINESS_RECOVERED"], signals)
        self.assertEqual(self.now + 115, self.scaler._DEADLINE)

    def test_real_unknown_create_is_single_attempt_and_never_reports_recovered(self):
        self.scaler.CAPACITY_ENABLED = True
        intent = "00000000-0000-4000-8000-000000000017"
        signals = []
        def authority(path, payload):
            if path == "alert":
                signals.append(payload["code"])
                return {}
            self.assertEqual("claim", path)
            return {"createAllowed": True, "intentId": intent, "nodeType": "test-size",
                    "nodeName": "test-stack-capacity-" + intent}
        self.scaler.capacity_request = authority
        with patch.object(self.scaler.urllib.request, "urlopen", side_effect=[
                self.response({"droplets": []}), self.response({"droplets": []}),
                urllib.error.URLError(TimeoutError("unknown creation"))]) as opener:
            result = self.invoke()
        self.assertEqual(["GET", "GET", "POST"], [call.args[0].method for call in opener.call_args_list])
        self.assertTrue(result["warning"].startswith("Provision outcome unknown"))
        self.assertEqual(["PROVISIONING_FAILED"], signals)

    def test_unknown_create_alert_precedes_quota_notices_when_finish_budget_is_tight(self):
        self.scaler.CAPACITY_ENABLED = True
        self.scaler._DEADLINE = 10.0
        signals = []
        response = types.SimpleNamespace(read=lambda limit: b"{}")
        def alert(request, timeout):
            signals.append(json.loads(request.data)["code"])
            self.advance(timeout)
            return contextlib.nullcontext(response)
        opener = Mock()
        opener.open.side_effect = alert
        with patch.object(self.scaler.urllib.request, "build_opener", return_value=opener):
            with contextlib.redirect_stdout(io.StringIO()):
                result = self.scaler.finish({"warning": "Provision outcome unknown; retain intent",
                    "readiness_verified": True, "waiting_for_capacity": True,
                    "alerts": [{"code": "ACCOUNT_DROPLET_QUOTA_PRESSURE"}]})["body"]
        self.assertEqual(["PROVISIONING_FAILED"], signals)
        self.assertEqual({"ACCOUNT_DROPLET_QUOTA_PRESSURE", "CAPACITY_WAITING"}, set(result["alert_delivery_failed"]))


class AutoscalerSafetyTest(unittest.TestCase):
    def test_alert_payload_has_integer_source_time_without_changing_action_result(self):
        scaler = load_autoscaler()
        scaler.CAPACITY_ENABLED = True
        calls = []
        scaler.capacity_request = lambda path, payload: calls.append((path, payload))
        with patch.object(scaler.time, 'time', return_value=1794441600.123):
            result = scaler.finish(dict(action='hold', readiness_verified=True))["body"]
        self.assertEqual([('alert', dict(stack='test-stack', code='READINESS_RECOVERED',
                                       observedAt=1794441600123))], calls)
        self.assertIs(type(calls[0][1]['observedAt']), int)
        self.assertEqual('hold', result['action'])
        self.assertTrue(result['readiness_verified'])
        self.assertNotIn('alert_delivery_failed', result)
        self.assertNotIn('observedAt', result)

    def test_readiness_wait_and_recovery_are_not_provisioning_failure(self):
        scaler = load_autoscaler()
        scaler.CAPACITY_ENABLED = True
        calls = []
        scaler.capacity_request = lambda path, payload: calls.append(payload['code'])
        scaler.finish({'readiness_wait': True, 'readiness_verified': True})
        self.assertEqual(['READINESS_UNAVAILABLE'], calls)
        calls.clear()
        scaler.finish({'readiness_verified': True})
        self.assertEqual(['READINESS_RECOVERED'], calls)
        calls.clear()
        scaler.finish({'error': 'Unknown creation receipt', 'readiness_verified': True})
        self.assertEqual(['PROVISIONING_FAILED'], calls)

    def test_only_explicit_pre_dispatch_503_is_a_readiness_wait(self):
        from unittest.mock import patch, Mock
        import urllib.error
        scaler = load_autoscaler()
        opener = Mock()
        with patch.object(scaler.urllib.request, 'build_opener', return_value=opener):
            for path, status, expected in [('claim', 503, scaler.ReadinessUnavailable),
                    ('claim-drain', 503, scaler.ReadinessUnavailable), ('observed', 503, RuntimeError),
                    ('claim', 403, RuntimeError)]:
                opener.open.side_effect = urllib.error.HTTPError('https://backend.example.test', status, 'error', {}, None)
                with self.assertRaises(expected) as caught:
                    scaler.capacity_request(path, {})
                self.assertEqual(expected, type(caught.exception))

    def test_alerts_are_delivered_and_delivery_failure_does_not_retry_provisioning(self):
        scaler = load_autoscaler()
        scaler.CAPACITY_ENABLED = True
        calls = []
        scaler.capacity_request = lambda path, payload: calls.append((path, payload))
        scaler.finish({"error": "synthetic failure", "waiting_for_capacity": True,
                       "alerts": [{"code": "ACCOUNT_DROPLET_QUOTA_PRESSURE"}]})
        self.assertEqual({"ACCOUNT_DROPLET_QUOTA_PRESSURE", "PROVISIONING_FAILED", "CAPACITY_WAITING"},
                         {payload["code"] for path, payload in calls})
        self.assertTrue(all(path == "alert" and payload["stack"] == "test-stack" for path, payload in calls))
        def failed(*args):
            raise RuntimeError("synthetic delivery failure")
        scaler.capacity_request = failed
        result = scaler.finish({"action": "hold", "error": "synthetic failure"})["body"]
        self.assertEqual(["PROVISIONING_FAILED"], result["alert_delivery_failed"])
        self.assertEqual("hold", result["action"])

    def test_quota_evidence_is_attached_to_claim(self):
        scaler = load_autoscaler()
        scaler.MAX_NODES = 0
        self.assertEqual({"accountDropletQuota": 25, "accountDropletCount": 4},
                         scaler.quota_claim_fields({"account_quota": 25, "account_droplets": 4}))
        with self.assertRaises(KeyError):
            scaler.quota_claim_fields({})

    def test_account_quota_mode_counts_other_stacks_and_emits_pressure_alert(self):
        scaler = load_autoscaler()
        scaler.MAX_NODES = 0
        calls = []
        def api(method, path):
            calls.append((method, path))
            return {"account": {"droplet_limit": 10}} if path == "/account" else {"meta": {"total": 8}}
        scaler.apicall = api
        result = {}
        self.assertEqual(5, scaler.account_fleet_limit(3, result))
        self.assertEqual("ACCOUNT_DROPLET_QUOTA_PRESSURE", result["alerts"][0]["code"])
        self.assertEqual([("GET", "/account"), ("GET", "/droplets?per_page=1")], calls)
        scaler.apicall = lambda method, path: {"account": {"droplet_limit": 10}} if path == "/account" else {"meta": {"total": 11}}
        self.assertEqual(3, scaler.account_fleet_limit(3, {}))

    def test_missing_quota_evidence_never_means_unlimited_creation(self):
        scaler = load_autoscaler()
        scaler.MAX_NODES = 0
        for response in (None, {}, [], {"account": None}, {"account": []},
                         {"account": {"droplet_limit": True}, "meta": {"total": 2}},
                         {"account": {"droplet_limit": 25}, "meta": None},
                         {"account": {"droplet_limit": 25}, "meta": []},
                         {"account": {"droplet_limit": 25}, "meta": {"total": True}},
                         {"account": {"droplet_limit": 25}, "meta": {"total": 1}}):
            scaler.apicall = lambda *args: response
            with self.assertRaises(RuntimeError):
                scaler.account_fleet_limit(2, {})
        scaler.MAX_NODES = 4
        scaler.apicall = lambda *args: self.fail("Fixed-cap mode must preserve existing behavior")
        self.assertEqual(4, scaler.account_fleet_limit(2, {}))

    def test_capacity_node_has_stack_ownership_on_all_creation_paths(self):
        for enabled in (False, True):
            for receipt in (False, True):
                scaler = load_autoscaler()
                scaler.CAPACITY_ENABLED = enabled
                calls = []
                scaler.apicall = lambda method, path, body: calls.append(body) or {"droplet": {"id": 99, "name": "test", "status": "new"}}
                with contextlib.redirect_stdout(io.StringIO()):
                    scaler.create_node(name="synthetic-node", return_receipt=receipt)
                self.assertEqual(["media", "test-stack"] if enabled else ["media"], calls[0]["tags"])

    def test_oversized_startup_is_rejected_before_provider_mutation(self):
        scaler = load_autoscaler()
        scaler.USER_DATA = "x" * 65537
        scaler.apicall = lambda *args: self.fail("Must not dispatch oversized startup")
        with self.assertRaisesRegex(RuntimeError, "64 KiB"):
            scaler.create_node()

    def setUp(self):
        self.autoscaler = load_autoscaler()

    def invoke(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.autoscaler.main({})["body"]

    def test_capacity_drain_delivers_only_exact_authorized_target(self):
        self.autoscaler.SCALE_IN_ENABLED = True
        calls = []
        receipt = {"dropletId": "2", "nodeId": "node-b", "generation": "boot-b",
                   "applicationExcluded": True, "applicationObligationsClear": False}
        self.autoscaler.capacity_request = lambda path, payload: calls.append((path, payload)) or receipt
        self.autoscaler.tag_res = lambda *args: calls.append(("tag", args)) or True
        self.autoscaler.untag_res = lambda *args: calls.append(("untag", args)) or True
        with contextlib.redirect_stdout(io.StringIO()):
            result = self.autoscaler.reconcile_capacity_drain([node(1, "a"), node(2, "b")], {"action": "hold"})["body"]
        self.assertEqual("scale-in-capacity", result["action"])
        self.assertEqual("claim-drain", calls[0][0])
        self.assertEqual(["1", "2"], calls[0][1]["allocatedDropletIds"])
        self.assertEqual([("tag", (2, "draining")), ("untag", (2, "media"))], calls[1:])

    def test_capacity_drain_failure_never_untags_or_chooses_another_node(self):
        self.autoscaler.SCALE_IN_ENABLED = True
        receipt = {"dropletId": "2", "nodeId": "node-b", "generation": "boot-b",
                   "applicationExcluded": True, "applicationObligationsClear": False}
        self.autoscaler.capacity_request = lambda *args: receipt
        tags = []
        self.autoscaler.tag_res = lambda *args: tags.append(args) or False
        self.autoscaler.untag_res = lambda *args: self.fail("Must retain active tag on failed drain delivery")
        with self.assertRaisesRegex(RuntimeError, "exclusion retained"):
            self.autoscaler.reconcile_capacity_drain([node(1, "a"), node(2, "b")], {})
        self.assertEqual([(2, "draining")], tags)
        receipt["dropletId"] = "99"
        with self.assertRaisesRegex(RuntimeError, "outside current fleet"):
            self.autoscaler.reconcile_capacity_drain([node(1, "a"), node(2, "b")], {})
        self.assertEqual([(2, "draining")], tags)

    def test_capacity_drain_replay_and_no_candidate_do_not_issue_new_mutations(self):
        self.autoscaler.SCALE_IN_ENABLED = True
        calls = []
        self.autoscaler.capacity_request = lambda path, payload: calls.append((path, payload)) or {}
        self.autoscaler.tag_res = lambda *args: self.fail("No new tag expected")
        self.autoscaler.untag_res = lambda *args: self.fail("No tag removal expected")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual("hold", self.autoscaler.reconcile_capacity_drain(
                [node(1, "a"), node(2, "b")], {"action": "hold"})["body"]["action"])
            self.autoscaler.capacity_request = lambda path, payload: calls.append((path, payload)) or {
                "dropletId": "2", "nodeId": "b", "generation": "boot",
                "applicationExcluded": True, "applicationObligationsClear": False}
            self.assertEqual("scale-in-capacity", self.autoscaler.reconcile_capacity_drain(
                [node(1, "a"), node(2, "b", ["draining"])], {})["body"]["action"])
        self.assertEqual(['claim-drain', 'claim-drain'], [path for path, _ in calls])
        self.assertTrue(all(payload['allocatedDropletIds'] == ['1', '2'] for _, payload in calls))

    def test_capacity_at_or_below_floor_does_not_claim_drain_or_report_provisioning_failure(self):
        for minimum, count in ((1, 0), (1, 1), (2, 1), (2, 2)):
            with self.subTest(allocated=count, minimum=minimum):
                self.autoscaler = load_autoscaler()
                claim, _, writes, _ = self.capacity_setup(False, count=count)
                claim.update(intentId=None, nodeName=None)
                self.autoscaler.MIN_NODES = minimum
                self.autoscaler.SCALE_IN_ENABLED = True
                calls, signals = [], []
                def authority(path, payload):
                    calls.append(path)
                    if path == 'claim': return claim
                    if path == 'alert':
                        signals.append(payload['code']); return {}
                    self.fail('Floor-sized fleet must not request drain authority')
                self.autoscaler.capacity_request = authority
                self.autoscaler.tag_res = lambda *args: self.fail('No cloud drain tag expected')
                self.autoscaler.untag_res = lambda *args: self.fail('No cloud tag removal expected')
                result = self.invoke()
                self.assertEqual('hold', result['action'])
                self.assertEqual('Fleet at minimum; no scale-in requested', result['warning'])
                self.assertNotIn('error', result)
                self.assertEqual(['claim', 'alert'], calls)
                self.assertEqual(['READINESS_RECOVERED'], signals)
                self.assertEqual([], writes)

    def test_scale_in_disabled_holds_low_cpu_even_above_maximum(self):
        for count in (2, 5):
            with self.subTest(count=count):
                self.autoscaler = load_autoscaler()
                writes = []
                self.autoscaler.list_nodes = lambda *args: ([] if args else [node(i, str(i)) for i in range(count)])
                self.autoscaler.cpu = lambda *args: 10
                self.autoscaler.tag_res = lambda *args: writes.append(args)
                result = self.invoke()
                self.assertEqual("hold", result["action"])
                self.assertIn("disabled", result["warning"])
                self.assertEqual([], writes)

    def test_scale_in_disabled_preserves_cpu_and_minimum_scale_out(self):
        for count, cpu, action in ((1, 90, "scale-out"), (0, 0, "scale-out-min")):
            with self.subTest(action=action):
                self.autoscaler = load_autoscaler()
                self.autoscaler.list_nodes = lambda *args: ([] if args else [node(i, str(i)) for i in range(count)])
                self.autoscaler.cpu = lambda *args: cpu
                creates = []
                self.autoscaler.create_node = lambda: creates.append(True) or {"id": 99}
                result = self.invoke()
                self.assertEqual(action, result["action"])
                self.assertEqual([True], creates)

    def capacity_setup(self, allowed=True, count=1):
        self.autoscaler.CAPACITY_ENABLED = True
        intent = "00000000-0000-4000-8000-000000000017"
        claim = {"createAllowed": allowed, "intentId": intent, "nodeType": "test-size",
                 "nodeName": "test-stack-capacity-" + intent}
        inventory = [node(i + 1, str(i + 1)) for i in range(count)]
        writes, observations = [], []
        def api(method, path, body=None):
            if method == "GET" and "tag_name=draining" in path:
                return {"droplets": []}
            if method == "GET" and path.startswith("/droplets?"):
                return {"droplets": inventory}
            if method == "POST" and path == "/droplets":
                writes.append(body)
                return {"droplet": node(99, body["name"])}
            raise AssertionError((method, path))
        def authority(path, payload):
            if path == "claim":
                return claim
            if path == "alert":
                return {}
            observations.append(payload)
            return {}
        self.autoscaler.apicall = api
        self.autoscaler.capacity_request = authority
        return claim, inventory, writes, observations

    def test_granted_intent_creates_one_named_node_and_records_receipt(self):
        claim, _, writes, observations = self.capacity_setup()
        result = self.invoke()
        self.assertEqual("scale-out-capacity", result["action"])
        self.assertEqual([claim["nodeName"]], [w["name"] for w in writes])
        self.assertEqual([{"intentId": claim["intentId"], "dropletId": "99"}], observations)

    def test_claim_sends_exact_active_and_draining_identities_not_just_count(self):
        self.capacity_setup(False, count=1)
        claims = []
        self.autoscaler.apicall = lambda method, path, body=None: {
            "droplets": [node(2, "draining", ["draining"])] if "tag_name=draining" in path else [node(1, "active")]}
        def authority(path, payload):
            claims.append(payload)
            return {"createAllowed": False, "intentId": None, "nodeName": None, "nodeType": "test-size"}
        self.autoscaler.capacity_request = authority
        self.invoke()
        self.assertEqual(["1", "2"], claims[0]["allocatedDropletIds"])
        self.assertEqual("test-size", claims[0]["nodeType"])
        self.assertNotIn("allocated", claims[0])

    def test_backend_inventory_disagreement_never_falls_back_to_create(self):
        _, _, writes, _ = self.capacity_setup(True, count=0)
        def authority(path, payload):
            raise RuntimeError("Allocated inventory differs from authoritative capacity snapshot")
        self.autoscaler.capacity_request = authority
        self.assertEqual("hold", self.invoke()["action"])
        self.assertEqual([], writes)

    def test_missing_or_mismatched_node_type_never_creates_or_observes(self):
        for value in (None, "larger-size", 8):
            claim, _, writes, observations = self.capacity_setup(True, count=0)
            claim["nodeType"] = value
            self.assertEqual("hold", self.invoke()["action"])
            self.assertEqual([], writes)
            self.assertEqual([], observations)

    def test_replay_with_wrong_node_type_is_not_observed_as_success(self):
        claim, inventory, writes, observations = self.capacity_setup(False)
        inventory.append(node(99, claim["nodeName"]))
        claim["nodeType"] = "another-size"
        self.assertEqual("hold", self.invoke()["action"])
        self.assertEqual([], writes)
        self.assertEqual([], observations)

    def test_wrong_size_existing_receipt_retains_unknown_intent(self):
        claim, inventory, writes, observations = self.capacity_setup(False)
        receipt = node(99, claim["nodeName"])
        receipt["size_slug"] = "different-size"
        inventory.append(receipt)
        self.assertEqual("hold", self.invoke()["action"])
        self.assertEqual([], writes)
        self.assertEqual([], observations)

    def test_replayed_claim_only_observes_and_does_not_create(self):
        claim, inventory, writes, observations = self.capacity_setup(False)
        self.invoke()
        self.assertEqual([], writes)
        inventory.append(node(99, claim["nodeName"]))
        self.invoke()
        self.assertEqual([], writes)
        self.assertEqual("99", observations[0]["dropletId"])

    def test_unknown_creation_response_is_not_retried(self):
        claim, inventory, writes, _ = self.capacity_setup()
        def uncertain(method, path, body=None):
            if method == "GET":
                return {"droplets": [] if "tag_name=draining" in path else inventory}
            writes.append(body)
            claim["createAllowed"] = False
            return None
        self.autoscaler.apicall = uncertain
        self.invoke()
        self.invoke()
        self.assertEqual(1, len(writes))

    def test_existing_named_outcome_is_reconciled_even_with_dispatch_grant(self):
        claim, inventory, writes, observations = self.capacity_setup()
        inventory.append(node(99, claim["nodeName"]))
        self.invoke()
        self.assertEqual([], writes)
        self.assertEqual("99", observations[0]["dropletId"])

    def test_capacity_mode_never_scales_in_or_falls_back_to_cpu(self):
        self.capacity_setup(False, count=3)
        self.autoscaler.capacity_request = lambda path, payload: {
            "createAllowed": False, "intentId": None, "nodeName": None, "nodeType": "test-size"}
        result = self.invoke()
        self.assertEqual("hold", result["action"])
        self.assertIn("holds automatic scale-in", result["warning"])

    def test_authority_failure_holds_even_below_minimum(self):
        _, _, writes, _ = self.capacity_setup(False, count=0)
        def failed(*args):
            raise RuntimeError("unavailable")
        self.autoscaler.capacity_request = failed
        self.assertEqual("hold", self.invoke()["action"])
        self.assertEqual([], writes)

    def test_readiness_hold_never_creates_and_only_sends_readiness_signal(self):
        _, _, writes, _ = self.capacity_setup(False, count=0)
        signals = []
        def waiting(path, payload):
            if path == 'alert':
                signals.append(payload['code'])
                return {}
            raise self.autoscaler.ReadinessUnavailable('Allocation held')
        self.autoscaler.capacity_request = waiting
        result = self.invoke()
        self.assertEqual('hold', result['action'])
        self.assertNotIn('error', result)
        self.assertEqual(['READINESS_UNAVAILABLE'], signals)
        self.assertEqual([], writes)

    def test_allocation_limit_is_rechecked_before_create(self):
        _, _, writes, _ = self.capacity_setup(True, count=4)
        self.assertIn("Allocation limit", self.invoke()["error"])
        self.assertEqual([], writes)

    def test_old_push_floor_is_rejected_before_cloud_calls(self):
        calls = []
        self.autoscaler.apicall = lambda *args: calls.append(args)
        with contextlib.redirect_stdout(io.StringIO()):
            result = self.autoscaler.main({"capacity": {"demand_revision": 19}})["body"]
        self.assertEqual("hold", result["action"])
        self.assertEqual([], calls)

    def test_duplicate_named_outcomes_fail_closed(self):
        claim, inventory, writes, _ = self.capacity_setup(False)
        inventory.extend([node(98, claim["nodeName"]), node(99, claim["nodeName"])])
        self.assertIn("Duplicate provision", self.invoke()["error"])
        self.assertEqual([], writes)

    def test_authority_requires_https_and_rejects_credential_redirects(self):
        self.autoscaler.CAPACITY_BACKEND_URL = "http://backend.example.test"
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            self.autoscaler.capacity_request("claim", {})
        with self.assertRaisesRegex(RuntimeError, "redirects are forbidden"):
            self.autoscaler.NoCapacityRedirects().redirect_request(None, None, 302, None, {}, "https://other.test")

    def test_observation_accepts_empty_success_response_without_logging_credentials(self):
        response = types.SimpleNamespace(read=lambda limit: b"")
        opener = types.SimpleNamespace(open=lambda request, timeout: contextlib.nullcontext(response))
        from unittest.mock import patch
        with patch.object(self.autoscaler.urllib.request, "build_opener", return_value=opener):
            self.assertEqual({}, self.autoscaler.capacity_request("observed", {"intentId": "test"}))

    def test_partial_inventory_cannot_grant_or_mutate_capacity(self):
        _, _, writes, observations = self.capacity_setup()
        self.autoscaler.apicall = lambda *args: {"droplets": [], "links": {"pages": {"next": "next-page"}}}
        result = self.invoke()
        self.assertIn("Incomplete paginated", result["warning"])
        self.assertTrue(result["readiness_wait"])
        self.assertNotIn("error", result)
        self.assertEqual([], writes)
        self.assertEqual([], observations)

    def test_inventory_failure_holds_capacity(self):
        calls = []

        def api(method, path, body=None):
            calls.append((method, path))
            return None

        self.autoscaler.apicall = api
        result = self.invoke()

        self.assertEqual("hold", result["action"])
        self.assertIn("inventory", result["warning"])
        self.assertTrue(result["readiness_wait"])
        self.assertNotIn("error", result)
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
        self.assertIn("tag metadata", result["warning"])
        self.assertTrue(result["readiness_wait"])
        self.assertNotIn("error", result)
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
                ("GET", "/droplets?tag_name=draining&per_page=200"),
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
        self.assertIn("0/2", result["warning"])
        self.assertTrue(result["readiness_wait"])
        self.assertNotIn("error", result)
        self.assertTrue(all(method == "GET" for method, _ in calls))

    def test_draining_only_nodes_count_toward_allocation_limit(self):
        writes = []
        def api(method, path, body=None):
            if method != 'GET':
                writes.append(path)
                return {}
            if 'tag_name=media' in path:
                return {'droplets': []}
            if 'tag_name=draining' in path:
                return {'droplets': [node(i, str(i), ['draining']) for i in range(4)]}
            raise AssertionError(path)
        self.autoscaler.apicall = api
        result = self.invoke()
        self.assertEqual('hold', result['action'])
        self.assertEqual(4, result['allocated_nodes'])
        self.assertEqual([], writes)

    def test_draining_inventory_failure_holds_without_mutation(self):
        self.autoscaler.apicall = lambda method, path, body=None: (
            {'droplets': [node(1, 'one')]} if 'tag_name=media' in path else None)
        result = self.invoke()
        self.assertEqual('hold', result['action'])
        self.assertIn('inventory', result['warning'])
        self.assertTrue(result['readiness_wait'])
        self.assertNotIn('error', result)

    def test_newer_draining_inventory_overrides_older_active_inventory(self):
        writes = []
        def api(method, path, body=None):
            if method != 'GET':
                writes.append(path)
                return {'droplet': node(2, 'replacement')}
            if 'tag_name=media' in path:
                return {'droplets': [node(1, 'one')]}
            if 'tag_name=draining' in path:
                return {'droplets': [node(1, 'one', ['draining'])]}
            raise AssertionError(path)
        self.autoscaler.apicall = api
        result = self.invoke()
        self.assertEqual('scale-out-min', result['action'])
        self.assertEqual(0, result['nodes'])
        self.assertEqual(1, result['allocated_nodes'])
        self.assertEqual(['/droplets'], writes)

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
        self.autoscaler.SCALE_IN_ENABLED = True
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
        self.autoscaler.SCALE_IN_ENABLED = True
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
        self.autoscaler.SCALE_IN_ENABLED = True
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
        self.autoscaler.SCALE_IN_ENABLED = True
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
