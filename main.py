import json

import yaml
import subprocess
import copy
import sys
import os
import argparse

HOME = os.path.expanduser('~')
TEMPLATE_DIR = os.path.join(os.getcwd(), 'templates')
OUTPUT_DIR = os.path.join(os.getcwd(), 'manifests')
NS_OUTPUT_PATH = os.path.join(os.getcwd(),"manifests/")
DEPLOYMENT_OUTPUT_PATH = os.path.join(os.getcwd(),"manifests/")
SERVICE_OUTPUT_PATH = os.path.join(os.getcwd(),"manifests/")
CR_OUTPUT_PATH = os.path.join(os.getcwd(),"manifests/")
TS_TEMPLATE_PATH = f"{TEMPLATE_DIR}/ts.yaml"
VS_TEMPLATE_PATH = f"{TEMPLATE_DIR}/vs-unsecured.yaml"
NS_TEMPLATE_PATH = f"{TEMPLATE_DIR}/ns.yaml"
DEPLOY_TEMPLATE_PATH = f"{TEMPLATE_DIR}/deploy.yaml"
SVC_TEMPLATE_PATH = f"{TEMPLATE_DIR}/svc.yaml"
MC_SVC_TEMPLATE_PATH = f"{TEMPLATE_DIR}/mc-svc.yaml"
NMC_SVC_TEMPLATE_PATH = f"{TEMPLATE_DIR}/nmc-svc.yaml"


def create_directory_if_not_exists(directory_path):
    """Create a directory if it does not exist."""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        print(f"Directory '{directory_path}' created.")

def read_yaml_file(file_path):
    """Read and return the contents of a YAML file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def write_multiple_resources(resources, dir_path, file_name):
    """Write multiple resources to a single YAML file."""
    create_directory_if_not_exists(dir_path)
    with open(dir_path+"/"+file_name, 'w') as file:
        for rsc in resources:
            yaml.safe_dump(rsc, file)
            file.write('---\n')


def create_resource(file_path, cluster):
    """Apply the resources using kubectl."""
    try:
        subprocess.run([f'kubectl', '--kubeconfig', f'{HOME}/kubeconfig{cluster}', 'create', '-f', file_path], check=True)
        print(f"Resource applied successfully from {file_path}.")
    except subprocess.CalledProcessError as e:
        print(f"Error applying resource: {e}")


def delete_ns(file_path, cluster):
    """Delete the resources using kubectl."""
    try:
        subprocess.run([f'kubectl', '--kubeconfig', f'{HOME}/kubeconfig{cluster}', 'delete', '-f', file_path], check=True)
        print(f"Resource deleted successfully from {file_path}.")
    except subprocess.CalledProcessError as e:
        print(f"Error deleting resource: {e}")

def get_vs_address(count):
    if count < 200:
        return f"10.8.4.{count}"
    else:
        return f"10.8.{(count//200) + 4}.{count%200}"


def generate_ts_scale(count, tenant_factor, total_clusters, ns_factor):
    """Generate TrafficSplit resources with scaling across clusters."""
    # Read templates
    base_ns = read_yaml_file(NS_TEMPLATE_PATH)
    base_deployment = read_yaml_file(DEPLOY_TEMPLATE_PATH)
    base_service = read_yaml_file(SVC_TEMPLATE_PATH)
    base_ts = read_yaml_file(TS_TEMPLATE_PATH)
    # Generate TS
    resource_type = "ts"
    tss_yaml = []
    deploys_yaml = dict()
    svcs_yaml = dict()
    nss_yaml = []
    svc_count = 1
    svc_port_start = 4999
    weights = [50, 20, 30]
    vs_port = 1000
    ts_count = 0
    for tenant_num in range(1, count//tenant_factor+1):
        ts_till_now = ts_count #0
        for ct in range(ts_till_now+1, ts_till_now+1+tenant_factor): # 1->100, 101->200, ..
            # TS
            ts_yaml = copy.deepcopy(base_ts)
            ts_yaml['metadata']['name'] = f"cr-{resource_type}-{ct}"
            ns_name = f"ns-{(ct // ns_factor)+1}"
            ts_yaml['metadata']['namespace'] = ns_name
            ts_yaml['spec']['virtualServerAddress'] = get_vs_address(ct)
            ts_yaml['spec']['virtualServerPort'] = vs_port
            ts_yaml['spec']['partition'] = f"test-{tenant_num}"
            vs_port += 1
            mcss = ts_yaml['spec']['pool']['multiClusterServices']
            final_mcss = []
            svc_port = svc_port_start + ct  # 5000, 5001, 5002 ...
            for i in range(len(mcss)):
                mcs = mcss[i]
                cluster_num = (svc_count-1) % total_clusters + 1 #1,2,3,4,5,1,2,3,...
                cluster_name= f"cluster{cluster_num}"
                mcs['clusterName'] = cluster_name
                deployment_name = cluster_name+"-deploy-"
                mcs['namespace'] = ns_name
                svc_name = f"{cluster_name}-svc-{svc_count}"
                deployment_name += str(svc_count)
                mcs['service'] = svc_name
                svc_count += 1
                mcs['servicePort'] = svc_port
                mcs['weight'] = weights[i]
                final_mcss.append(mcs)
                new_deploy_yaml = generate_deploy_yaml(base_deployment, deployment_name, ns_name, svc_port)
                new_svc_yaml = generate_svc_yaml(base_service, svc_name, ns_name, svc_port, deployment_name)
                if cluster_num in deploys_yaml:
                    deploys_yaml[cluster_num].append(new_deploy_yaml)
                    svcs_yaml[cluster_num].append(new_svc_yaml)
                else:
                    deploys_yaml[cluster_num] = [new_deploy_yaml]
                    svcs_yaml[cluster_num] = [new_svc_yaml]
            ts_yaml['spec']['pool']['multiClusterServices'] = final_mcss
            tss_yaml.append(ts_yaml)
            ts_count += 1
    write_multiple_resources(tss_yaml, CR_OUTPUT_PATH + str(count) + f"/{resource_type}", f"{resource_type}-" + str(count) + ".yaml")
    for cluster_key in deploys_yaml.keys():
        write_multiple_resources(deploys_yaml[cluster_key], DEPLOYMENT_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/deploy", "deploy-cluster" + str(cluster_key) + ".yaml")
    for cluster_key in svcs_yaml.keys():
        write_multiple_resources(svcs_yaml[cluster_key], SERVICE_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/svc", "svc-cluster" + str(cluster_key) + ".yaml")
    for ct in range(1, (count // ns_factor)+3):
        ns_yaml = copy.deepcopy(base_ns)
        ns_yaml['metadata']['name'] = f"ns-{ct}"
        nss_yaml.append(ns_yaml)
    for cl_ct in range(1, total_clusters+1):
        write_multiple_resources(nss_yaml, NS_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/ns", "ns-cluster" + str(cl_ct) + ".yaml")

def generate_deploy_yaml(base_deploy_yaml, name, ns, port):
    deploy_yaml = copy.deepcopy(base_deploy_yaml)
    deploy_yaml['metadata']['name'] = name
    deploy_yaml['metadata']['namespace'] = ns
    deploy_yaml['spec']['selector']['matchLabels']['app'] = name
    deploy_yaml['spec']['template']['metadata']['labels']['app'] = name
    deploy_yaml['spec']['template']['spec']['containers'][0]['name'] = name
    deploy_yaml['spec']['template']['spec']['containers'][0]['ports'][0]['containerPort'] = port
    deploy_yaml['spec']['template']['spec']['containers'][0]['env'][0]['value'] = str(port)
    return deploy_yaml


def generate_svc_yaml(base_service_yaml, name, ns, port, deploy_name, annotations=None):
    svc_yaml = copy.deepcopy(base_service_yaml)
    svc_yaml['metadata']['name'] = name
    svc_yaml['metadata']['namespace'] = ns
    svc_yaml['metadata']['labels']['app'] = name
    if annotations:
        svc_yaml['metadata']['annotations'] = annotations

    svc_yaml['spec']['ports'][0]['name'] = name+f'-{str(port)}'
    svc_yaml['spec']['ports'][0]['port'] = port
    svc_yaml['spec']['ports'][0]['targetPort'] = port

    svc_yaml['spec']['selector']['app'] = deploy_name
    return svc_yaml

def create_resources(count, total_clusters, rsc_type):
    # 1. create ns
    for i in range(1,total_clusters+1):
        create_resource(NS_OUTPUT_PATH + str(count) + f"/{rsc_type}" + "/ns/ns-cluster" + str(i) + ".yaml", i)
    # 2. Create DEPLOY
    for i in range(1,total_clusters+1):
        create_resource(DEPLOYMENT_OUTPUT_PATH + str(count) + f"/{rsc_type}" + "/deploy/deploy-cluster" + str(i) + ".yaml", i)
    # 3. Create SVC
    for i in range(1,total_clusters+1):
        create_resource(SERVICE_OUTPUT_PATH + str(count) + f"/{rsc_type}" + "/svc/svc-cluster" + str(i) + ".yaml", i)
    # 4. Create TS
    if rsc_type != "nmsvclb" and rsc_type != "mcsvclb":
        for i in range(1,3):
            create_resource(CR_OUTPUT_PATH + str(count) + f"/{rsc_type}" + f"/{rsc_type}-" + str(count) + ".yaml", i)

def generate_vs_scale(count, tenant_factor, total_clusters,  ns_factor):
    # Read ns
    resource_type = "vs"
    base_ns = read_yaml_file(NS_TEMPLATE_PATH)
    base_deployment = read_yaml_file(DEPLOY_TEMPLATE_PATH)
    base_service = read_yaml_file(SVC_TEMPLATE_PATH)
    base_vs = read_yaml_file(VS_TEMPLATE_PATH)
    # Generate VS
    vss_yaml = []
    deploys_yaml = dict()
    svcs_yaml = dict()
    nss_yaml = []
    svc_count = 1
    svc_port_start = 4999
    weights = [50, 20, 30]
    vs_port = 1000
    vs_count = 0
    for tenant_num in range(1, count//tenant_factor+1):
        vs_till_now = vs_count #0
        for ct in range(vs_till_now+1, vs_till_now+1+tenant_factor): # 1->100, 101->200, ..
            # TS
            vs_yaml = copy.deepcopy(base_vs)
            vs_yaml['metadata']['name'] = f"cr-{resource_type}-{ct}"
            ns_name = f"ns-{(ct // ns_factor)+1}"
            vs_yaml['metadata']['namespace'] = ns_name
            vs_yaml['spec']['virtualServerAddress'] = get_vs_address(ct)
            vs_yaml['spec']['virtualServerHTTPPort'] = vs_port
            vs_yaml['spec']['host'] = f"{resource_type}-{ct}.com"
            vs_yaml['spec']['partition'] = f"test-{tenant_num}"
            vs_port += 1
            mcss = vs_yaml['spec']['pools'][0]['multiClusterServices']
            final_mcss = []
            svc_port = svc_port_start + ct  # 5000, 5001, 5002 ...
            for i in range(len(mcss)):
                mcs = mcss[i]
                cluster_num = (svc_count-1) % total_clusters + 1 #1,2,3,4,5,1,2,3,...
                cluster_name= f"cluster{cluster_num}"
                mcs['clusterName'] = cluster_name
                deployment_name = cluster_name+"-deploy-"
                mcs['namespace'] = ns_name
                svc_name = f"{cluster_name}-svc-{svc_count}"
                deployment_name += str(svc_count)
                mcs['service'] = svc_name
                svc_count += 1
                mcs['servicePort'] = svc_port
                mcs['weight'] = weights[i]
                final_mcss.append(mcs)

                new_deploy_yaml = generate_deploy_yaml(base_deployment, deployment_name, ns_name, svc_port)
                new_svc_yaml = generate_svc_yaml(base_service, svc_name, ns_name, svc_port, deployment_name)
                if cluster_num in deploys_yaml:
                    deploys_yaml[cluster_num].append(new_deploy_yaml)
                    svcs_yaml[cluster_num].append(new_svc_yaml)
                else:
                    deploys_yaml[cluster_num] = [new_deploy_yaml]
                    svcs_yaml[cluster_num] = [new_svc_yaml]
            vs_yaml['spec']['pools'][0]['multiClusterServices'] = final_mcss
            vss_yaml.append(vs_yaml)
            vs_count += 1
    write_multiple_resources(vss_yaml, CR_OUTPUT_PATH + str(count) + f"/{resource_type}", f"{resource_type}-" + str(count) + ".yaml")
    for cluster_key in deploys_yaml.keys():
        write_multiple_resources(deploys_yaml[cluster_key], DEPLOYMENT_OUTPUT_PATH + str(count) + f"/{resource_type}" +"/deploy", "deploy-cluster" + str(cluster_key) + ".yaml")
    for cluster_key in svcs_yaml.keys():
        write_multiple_resources(svcs_yaml[cluster_key], SERVICE_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/svc", "svc-cluster" + str(cluster_key) + ".yaml")
    for ct in range(1, (count // ns_factor)+3):
        ns_yaml = copy.deepcopy(base_ns)
        ns_yaml['metadata']['name'] = f"ns-{ct}"
        nss_yaml.append(ns_yaml)
    for cl_ct in range(1, total_clusters+1):
        write_multiple_resources(nss_yaml, NS_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/ns", "ns-cluster" + str(cl_ct) + ".yaml")

def generate_nmc_svc(count, tenant_factor, total_clusters,  ns_factor):
    # Read ns
    resource_type = "nmsvclb"
    base_ns = read_yaml_file(NS_TEMPLATE_PATH)
    base_deployment = read_yaml_file(DEPLOY_TEMPLATE_PATH)
    # base_service = read_yaml_file(SVC_TEMPLATE_PATH)
    base_nmc_svc = read_yaml_file(NMC_SVC_TEMPLATE_PATH)
    # Generate VS
    deploys_yaml = dict()
    nmc_svcs_yaml = dict()
    nss_yaml = []
    ns_factor = 20 # 50 vs per ns (1, 10, 20, 50)
    vs_port = 1000
    vs_count = 0
    for tenant_num in range(1, count//tenant_factor+1):
        vs_till_now = vs_count #0
        for ct in range(vs_till_now+1, vs_till_now+1+tenant_factor): # 1->100, 101->200, ..
            # TS
            nmc_svc_yaml = copy.deepcopy(base_nmc_svc)
            vs_name = f"cr-{resource_type}-{ct}"
            nmc_svc_yaml['metadata']['name'] = vs_name
            ns_name = f"ns-{(ct // ns_factor)+1}"
            nmc_svc_yaml['metadata']['namespace'] = ns_name
            nmc_svc_yaml['metadata']['annotations']['cis.f5.com/ip'] = get_vs_address(ct)
            nmc_svc_yaml['spec']['ports'][0]['port'] = vs_port
            nmc_svc_yaml['spec']['ports'][0]['port'] = vs_port
            nmc_svc_yaml['spec']['ports'][0]['targetPort'] = vs_port
            #ts_yaml['spec']['partition'] = f"test-{tenant_num}"
            cluster_num = (ct % total_clusters) + 1  # 1,2,3,4,5,1,2,3,...
            cluster_name = f"cluster{cluster_num}"
            deployment_name = cluster_name + "-deploy-" + str(ct)

            new_deploy_yaml = generate_deploy_yaml(base_deployment, deployment_name, ns_name, vs_port)
            new_svc_yaml = generate_svc_yaml(base_nmc_svc, vs_name, ns_name, vs_port, deployment_name, annotations=nmc_svc_yaml['metadata']['annotations'])
            if cluster_num in deploys_yaml:
                deploys_yaml[cluster_num].append(new_deploy_yaml)
                nmc_svcs_yaml[cluster_num].append(new_svc_yaml)
            else:
                deploys_yaml[cluster_num] = [new_deploy_yaml]
                nmc_svcs_yaml[cluster_num] = [new_svc_yaml]

            vs_port += 1
            vs_count += 1
    for cluster_key in deploys_yaml.keys():
        write_multiple_resources(deploys_yaml[cluster_key], DEPLOYMENT_OUTPUT_PATH + str(count) + f"/{resource_type}" +"/deploy", "deploy-cluster" + str(cluster_key) + ".yaml")
    for cluster_key in nmc_svcs_yaml.keys():
        write_multiple_resources(nmc_svcs_yaml[cluster_key], SERVICE_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/svc", "svc-cluster" + str(cluster_key) + ".yaml")
    for ct in range(1, (count // ns_factor)+3):
        ns_yaml = copy.deepcopy(base_ns)
        ns_yaml['metadata']['name'] = f"ns-{ct}"
        nss_yaml.append(ns_yaml)
    for cl_ct in range(1, total_clusters+1):
        write_multiple_resources(nss_yaml, NS_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/ns", "ns-cluster" + str(cl_ct) + ".yaml")

def generate_mc_svc(count, tenant_factor, total_clusters,  ns_factor):
    # Read ns
    base_ns = read_yaml_file(NS_TEMPLATE_PATH)
    base_deployment = read_yaml_file(DEPLOY_TEMPLATE_PATH)
    base_mc_svc = read_yaml_file(MC_SVC_TEMPLATE_PATH)
    # Generate TS
    resource_type = "mcsvclb"
    deploys_yaml = dict()
    svcs_yaml = dict()
    nss_yaml = []
    svc_count = 1
    weights = [50, 20, 30]
    vs_port = 1000
    mcsvclb_count = 0
    mc_svc_yaml = copy.deepcopy(base_mc_svc)
    mcss_str = mc_svc_yaml['metadata']['annotations']['cis.f5.com/multiClusterServices']
    mcss = json.loads(mcss_str)
    for tenant_num in range(1, count//tenant_factor+1):
        ts_till_now = mcsvclb_count #0
        for ct in range(ts_till_now+1, ts_till_now+1+tenant_factor): # 1->100, 101->200, ..
            # TS
            svc_name = f"{resource_type}-{ct}"
            ns_name = f"ns-{(ct // ns_factor)+1}"
            mc_svclb_ip = get_vs_address(ct)
            #ts_yaml['spec']['partition'] = f"test-{tenant_num}"
            vs_port += 1
            final_mcss = []
            deployment_name = f"deploy-{ct}"
            tmp_svc_ct = svc_count
            for i in range(len(mcss)):
                mcs = mcss[i]
                cluster_num = (tmp_svc_ct-1) % total_clusters + 1 #1,2,3,4,5,1,2,3,...
                cluster_name= f"cluster{cluster_num}"
                mcs['clusterName'] = cluster_name
                tmp_svc_ct += 1
                mcs['weight'] = weights[i]
                final_mcss.append(mcs)

            added_to_cluster1 = False
            for i in range(len(mcss)):
                mcs = mcss[i]
                cluster_num = (svc_count-1) % total_clusters + 1 #1,2,3,4,5,1,2,3,...
                cluster_name= f"cluster{cluster_num}"
                mcs['clusterName'] = cluster_name
                svc_count += 1
                mcs['weight'] = weights[i]
                # final_mcss.append(mcs)
                new_deploy_yaml = generate_deploy_yaml(base_deployment, deployment_name, ns_name, vs_port)
                new_svc_yaml = generate_svc_yaml(base_mc_svc, svc_name, ns_name, vs_port, deployment_name)
                new_svc_yaml['metadata']['annotations']['cis.f5.com/multiClusterServices'] = json.dumps(final_mcss)
                new_svc_yaml['metadata']['annotations']['cis.f5.com/ip'] = mc_svclb_ip
                if cluster_num in svcs_yaml:
                    deploys_yaml[cluster_num].append(new_deploy_yaml)
                    svcs_yaml[cluster_num].append(new_svc_yaml)
                else:
                    deploys_yaml[cluster_num] = [new_deploy_yaml]
                    svcs_yaml[cluster_num] = [new_svc_yaml]
                if cluster_num == 1:
                    added_to_cluster1 = True
                if i == 2 and not added_to_cluster1:
                    if cluster_num in svcs_yaml:
                        svcs_yaml[1].append(new_svc_yaml)
                    else:
                        svcs_yaml[1] = [new_svc_yaml]
            mcsvclb_count += 1
    for cluster_key in deploys_yaml.keys():
        write_multiple_resources(deploys_yaml[cluster_key], DEPLOYMENT_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/deploy", "deploy-cluster" + str(cluster_key) + ".yaml")
    for cluster_key in svcs_yaml.keys():
        write_multiple_resources(svcs_yaml[cluster_key], SERVICE_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/svc", "svc-cluster" + str(cluster_key) + ".yaml")
    for ct in range(1, (count // ns_factor)+3):
        ns_yaml = copy.deepcopy(base_ns)
        ns_yaml['metadata']['name'] = f"ns-{ct}"
        nss_yaml.append(ns_yaml)
    for cl_ct in range(1, total_clusters+1):
        write_multiple_resources(nss_yaml, NS_OUTPUT_PATH + str(count) + f"/{resource_type}" + "/ns", "ns-cluster" + str(cl_ct) + ".yaml")

# Configuration with defaults that can be overridden
DEFAULT_CONFIG = {
    "total_clusters": 5,
    "ns_factor": 20,  # Resources per namespace
    "svc_port_start": 4999,
    "vs_port_start": 1000,
    "weights": [50, 20, 30]
}

def parse_arguments():
    """Parse command line arguments with better help and options."""
    parser = argparse.ArgumentParser(
        description="Generate Kubernetes manifests for testing multi-cluster services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--app_count", type=int, choices=[100, 500, 1000], default=100,
                        help="Number of Applications to generate")
    # parser.add_argument("--tenants", default=1,
    #                     help="Number of apps per tenant")
    parser.add_argument("--resource_type", choices=["ts", "vs", "nmsvclb", "mcsvclb"], required=True,
                        help="Type of resource to generate")
    parser.add_argument("--action", choices=["generate", "create", "delete"], default="generate",
                        help="Action to perform")
    # parser.add_argument("--clusters", type=int, default=DEFAULT_CONFIG["total_clusters"],
    #                     help="Number of clusters to generate resources for")
    # parser.add_argument("--namespaces", type=int, default=20,
    #                     help="Number of namespaces to generate resources in")
    return parser.parse_args()


def main():
    """Main function to orchestrate manifest generation and resource management."""
    args = parse_arguments()
    app_count = args.app_count
    tenants = 1
    clusters = 5
    namespaces = 20
    # Execute requested action
    if args.action in ["generate", "create", "delete"]:
        if args.resource_type == "ts":
            generate_ts_scale(app_count, tenants, clusters, namespaces)
        if args.resource_type == "vs":
            generate_vs_scale(app_count, tenants, clusters, namespaces)
        if args.resource_type == "nmsvclb":
            generate_nmc_svc(app_count, tenants, clusters, namespaces)
        if args.resource_type == "mcsvclb":
            generate_mc_svc(app_count, tenants, clusters, namespaces)
        if args.action == "create":
            create_resources(app_count, clusters, args.resource_type)
        elif args.action == "delete":
            for cluster_count in range(1, clusters+1):
                delete_ns(NS_OUTPUT_PATH + str(app_count) + f"/{args.resource_type}" + "/ns/ns-cluster" + str(cluster_count) + ".yaml", cluster_count)
    print(f"Successfully completed {args.action} for {str(app_count)} {args.resource_type} resources")
    return 0

if __name__ == '__main__':
    sys.exit(main())
