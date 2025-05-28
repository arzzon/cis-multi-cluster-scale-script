*CIS Multi-Cluster Resource Generator For Performance Analysis*

A configurable tool for generating, deploying, and deleting Kubernetes resources across multiple clusters. 
This tool is designed to help with scale testing of various resources(VirtualServer, TransportServer, MultiClusterServiceTypeLB and Non-MultiClusterServiceTypeLB) in multi-cluster environment.

**Features**

Generate various Kubernetes resource types (TransportServer, VirtualServer, Non-Multicluster Services, MultiCluster Services)

Scale resources across multiple clusters
Create, delete, or just generate resource manifests

***Prerequisites***

* Python 3.9+
* PyYAML
* 5 K8S Clusters are created
* kubectl configured for your target clusters

All kubeconfig files for all the target clusters should be stored in the home directory as follows:
```
$HOME/kubeconfig1
$HOME/kubeconfig2
$HOME/kubeconfig3
$HOME/kubeconfig4
$HOME/kubeconfig5
```
_**NOTE: kubeconfig file names should be kept as mentioned above(for cluster1 -> kubeconfig1, for cluster2 -> kubeconfig2, etc..)**_

***Installation***

Clone this repository:

```git clone https://github.com/arzzon/cis-multi-cluster-scale-script.git```

```cd k8s-multi-cluster-generator```

Install dependencies:

```pip install -r requirements.txt```


***Usage***

python main.py --app_count <app_count> --resource_type <resource_type> --action <action>

Where:

```app_count```: Number of resources to generate. For example you may want to create 100 VS.

```resource_type```: Type of resource to generate (Supported values: ts, vs, nmsvclb, mcsvclb)

```action```: Action to perform (generate, create, delete)


**Configuration Options**

| Option | Description | Default | Supported Values  | 
|--------|-------------|---------| ---------| 
| --app_count | Number of resources to generate | NA | 100 and 500 |
| --resource_type | Type of resource | NA | vs, ts, nmsvclb, mcsvclb |
| --action | Action you want to perform | NA | generate, create, delete |


**Supported app_count values**

| Option | Description |
|--------|-------------|
|  100 | 100 VS/TS/MultiClusterSvcTypeLBs/Non-MultiClusterSvcTypeLBs will be deployed |
|  500 | 500 VS/TS/MultiClusterSvcTypeLBs/Non-MultiClusterSvcTypeLBs will be deployed |


**Supported Resource Types**

| Option | Description |
|--------|-------------|
|  vs | Virtual Server |
|  ts | Transport Server |
|  nmsvclb | Non-Multicluster ServiceTypeLB |
|  mcsvclb | Multicluster ServiceTypeLB |


**Supported Actions**

| Option | Description |
|--------|-------------|
|  generate | Only generates all the manifest files like deployments,services,vs/ts CRs |
|  create | Generates and deploys all the manifest files like deployments,services,vs/ts CRs |
|  delete | Removes all the resources like deployments,services,vs/ts CRs |

Examples:


Generate 100 vs resource manifests

python main.py --app_count 100 --resource_type vs --action generate


Create 100 VirtualServer resources

python main.py --app_count 100 --resource_type vs --action create

Delete previously created resources:

python main.py --app_count 100 --resource_type vs --action delete


*Template Files*

The generator uses YAML templates for creating resources:

ns.yaml: Namespace template

deploy.yaml: Deployment template

svc.yaml: Service template

ts.yaml: TransportServer template

vs-unsecured.yaml: VirtualServer template

mc-svc.yaml: MultiClusterService template

nmc-svc.yaml: Non-MultiClusterService template

Output Structure

Generated resources are organized in the following directory structure:

```
output_dir/
└── <count>/
    └── <resource_type>/
        ├── cr/
        │   └── <resource_type>-<count>.yaml
        ├── deploy/
        │   └── deploy-cluster<n>.yaml
        ├── ns/
        │   └── ns-cluster<n>.yaml
        └── svc/
            └── svc-cluster<n>.yaml
```

**How it works?**

When you run the script to deploy certain number of resource for example 100 Transport Servers then the following things will be done:
1. Manifest file with 100 Transport Server CRs will be generated.
2. For each Transport Server 3 services will be added as multiClusterServices
3. Each service is linked with a deployment of an application.
4. The services and deployments are distributed uniformly among 5 k8s clusters.
