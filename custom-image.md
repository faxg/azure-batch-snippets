# End-to-End Azure Batch Deployment with Custom Ubuntu Image in Switzerland North

## Prerequisites
1. Azure subscription with **Owner** or **Contributor** permissions
2. Azure CLI installed (`az --version` ≥ 2.57.0). Or use the Cloud shell in the Azure portal.
3. Existing resource group in `switzerlandnorth` called `PrepGroup`
4. Prepared Ubuntu 20.04 VM in `switzerlandnorth` with:
   - Required libraries installed
   - Azure Linux Agent (waagent) configured
   - No sensitive data (already deprovisioned if needed)
5. Storage account in `switzerlandnorth` with:
   - Azure File share named `batchdata`
   - Python scripts uploaded to `scripts/` directory
   - Input data in `inputs/` directory

---

## 1. Create Generalized Image
Azure Node Pools only support "generalized" images.

### 1.1 Prepare Source VM
```bash
az vm run-command invoke -g PrepGroup -n SourceVM
--command-id RunShellScript
--scripts "sudo waagent -deprovision+user -force"
--query "value.message" -o tsv

az vm deallocate -g PrepGroup -n SourceVM --no-wait
az vm generalize -g PrepGroup -n SourceVM

```

### 1.2 Create Compute Gallery
```bash
az sig create
--resource-group PrepGroup
--gallery-name CHGallery
--location switzerlandnorth
```


### 1.3 Define Image
```bash
az sig image-definition create
--resource-group PrepGroup
--gallery-name CHGallery
--gallery-image-definition UbuntuBatch
--publisher MyOrg
--offer BatchReady
--sku 20.04-LTS
--os-type Linux
--os-state Generalized
--hyper-v-generation V2
```


### 1.4 Create Image Version

```bash
az sig image-version create
--resource-group PrepGroup
--gallery-name CHGallery
--gallery-image-definition UbuntuBatch
--gallery-image-version 1.0.0
--target-regions switzerlandnorth
--virtual-machine /subscriptions/{sub-id}/resourceGroups/PrepGroup/providers/Microsoft.Compute/virtualMachines/SourceVM
```


---

## 2. Configure Storage & Batch

### 2.1 Create Storage Account
```bash
az storage account create
--name chbatchstorage
--resource-group PrepGroup
--location switzerlandnorth
--sku Standard_LRS
--allow-blob-public-access false
```


### 2.2 Create File Share
```bash
az storage share create
--name batchdata
--account-name chbatchstorage
```

### 2.3 Upload Assets
```bash
az storage file upload-batch
--destination batchdata
--source ./local_scripts
--account-name chbatchstorage
--destination-path scripts/
```

---

## 3. Configure Batch Account

### 3.1 Create Batch Account
```batch
az batch account create
--name chbatch
--resource-group PrepGroup
--location switzerlandnorth
--identity-type SystemAssigned
```


### 3.2 Grant Image Access
#### Get managed identity ID
Note: A Service Principal (SP) in Microsoft Entra ID is like a special account that lets an application or service access resources securely. Think of it as a "login" for apps—instead of using a regular user account, apps use a Service Principal to authenticate and get permissions to do things like read data or interact with other services. 
A "Managed Identity" is essentially  a special kind of Service Principal, so you don't need to manually handle credentials or secrets.

```bash
batch_sp=$(az batch account show -n chbatch -g PrepGroup --query identity.principalId -o tsv)
```


#### Grant Reader role on gallery
```bash
gallery_id=$(az sig show -g PrepGroup --gallery-name CHGallery --query id -o tsv)

az role assignment create
--assignee $batch_sp
--role Reader
--scope $gallery_id
```


---

## 4. Create Batch Pool

### 4.1 Generate Pool Config
Create a `pool-config.json` file with this content (substitute subscription Ids and names):

```json
{
"id": "MiniPool",
"vmSize": "Standard_B1s",
"virtualMachineConfiguration": {
"imageReference": {
"id": "/subscriptions/{sub-id}/resourceGroups/PrepGroup/providers/Microsoft.Compute/galleries/CHGallery/images/UbuntuBatch/versions/1.0.0"
},
"nodeAgentSkuId": "batch.node.ubuntu 20.04"
},
"targetDedicatedNodes": 2,
"mountConfiguration": [{
"azureFileShareConfiguration": {
"accountName": "chbatchstorage",
"azureFileUrl": "https://chbatchstorage.file.core.windows.net/batchdata",
"accountKey": "$(az storage account keys list --account-name chbatchstorage --query .value -o tsv)",
"relativeMountPath": "mnt/data"
}
}]
}
```


### 4.2 Create Pool

```bash
az batch pool create
--json-file pool-config.json
--account-name chbatch
--resource-group PrepGroup
```


---

## 5. Submit Jobs

### 5.1 Create Job
```bash
az batch job create
--id DataProcessingJob
--pool-id MiniPool
--account-name chbatch
--resource-group PrepGroup
```


### 5.2 Submit Parameterized Tasks

```bash
for i in {1..3}; do
az batch task create
--job-id DataProcessingJob
--task-id task$i
--command-line "/bin/bash -c 'python3 /mnt/data/scripts/process.py --input /mnt/data/inputs/input${i}.csv --output /mnt/data/outputs/result${i}.txt'"
--account-name chbatch
--resource-group PrepGroup
done
```



---

## Validation Steps

1. Check pool allocation:
```bash
az batch pool show --pool-id MiniPool
--query "allocationState"
--account-name chbatch
```


2. Monitor task status:
```bash
az batch task list --job-id DataProcessingJob
--query "[].{Task:id, State:state}"
-o table
--account-name chbatch
```


3. Retrieve output:
```bash
az storage file download-batch
--source batchdata/outputs
--destination ./results
--account-name chbatchstorage
```


---

## Key Configuration Details

| Component              | Switzerland North Settings       |
|------------------------|-----------------------------------|
| **VM Size**            | Standard_B1s (1 vCPU, 1 GiB RAM) |
| **Storage Redundancy** | LRS                               |
| **Image Replication**  | Single region replication         |
| **Network**            | Default Azure networking          |

---

## Troubleshooting Checklist

1. **Image Validation**

```bash
az sig image-version show -g PrepGroup --gallery-name CHGallery
--gallery-image-definition UbuntuBatch --gallery-image-version 1.0.0
--query "[name, storageProfile.osDiskImage.osType, storageProfile.osDiskImage.osState]"
```


2. **File Share Permissions**

```bash
az storage file list --share-name batchdata
--account-name chbatchstorage
--path "scripts"
--query "[].name"
```


3. **Batch Identity Permissions**
```bash
az role assignment list --assignee $batch_sp
--scope $gallery_id
--query "[].roleDefinitionName"
```


4. **Node Connectivity**

```bash
az batch node list --pool-id MiniPool
--query "[].{Node:id, State:state}"
-o table
--account-name chbatch
```
