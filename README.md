# openvidu-digitalocean

## CourseUltra production deployment

This fork contains CourseUltra's pinned OpenVidu Elastic deployment under `pro/elastic`. CourseUltra
operators must begin with [`pro/elastic/COURSEULTRA.md`](pro/elastic/COURSEULTRA.md) and run Terraform
through `courseultra-terraform.sh`; the generic upstream installation links below do not include the
deployment's secret boundaries, remote state, drain ordering, recording checks, or cutover rules.

Terraform files to deploy all the types of deployments of OpenVidu in Digital Ocean cloud. You can check the documentation for the deployments in the following links: 
1. [Single Node Community deployment](https://openvidu.io/latest/docs/self-hosting/single-node/digitalocean/install)
2. [Single Node PRO deployment](https://openvidu.io/latest/docs/self-hosting/single-node-pro/digitalocean/install)
3. [Elastic deployment](https://openvidu.io/latest/docs/self-hosting/elastic/digitalocean/install)
4. [High Availability deployment](https://openvidu.io/latest/docs/self-hosting/ha/digitalocean/install)
