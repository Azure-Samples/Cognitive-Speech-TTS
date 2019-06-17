// <copyright file="StorageHelper.cs" company="Microsoft Corporation">
// Copyright (c) Microsoft Corporation. All rights reserved.
// </copyright>

namespace ConsoleApp1
{
    using System;
    using System.Threading.Tasks;
    using Microsoft.WindowsAzure.Storage.Blob;

    public static class StorageHelper
    {
        public static void UploadFileAsync(CloudBlobContainer container, string blobName, string localFilePath)
        {
            var blob = container.GetBlockBlobReference(blobName);
            blob.UploadFromFile(localFilePath);
        }


        public static string GetBlobSas(CloudBlobClient blobClient, string containerName, string blobName, DateTime expirationTime)
        {
            SharedAccessBlobPolicy sasConstraints = new SharedAccessBlobPolicy
            {
                SharedAccessExpiryTime = expirationTime,
                Permissions = SharedAccessBlobPermissions.Read | SharedAccessBlobPermissions.List
            };

            var container = blobClient.GetContainerReference(containerName);
            var blob = container.GetBlobReference(blobName);

            // Construct the SAS URL for container
            string sasContainerToken = blob.GetSharedAccessSignature(sasConstraints);
            string blobSasUri = blob.Uri + sasContainerToken;

            return blobSasUri;
        }
    }
}
