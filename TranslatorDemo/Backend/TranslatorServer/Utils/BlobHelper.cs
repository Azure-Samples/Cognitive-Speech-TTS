using Microsoft.WindowsAzure.Storage;
using Microsoft.WindowsAzure.Storage.Blob;
using System;
using System.Collections.Generic;
using System.IO;

namespace TranslatorServer.Utils
{
    public class BlobHelper
    {
        const string ConnectString = Configuration.BlobConnectString;
        const string ContainerName = Configuration.BlobContainerName;
        const string URLPrefix = Configuration.BlobURLPrefix;

        public static string SaveToBlob(string fileName, Stream sstream)
        {
            byte[] audioByte;
            try
            {
                using (MemoryStream ms = new MemoryStream())
                {
                    int count = 0;
                    do
                    {
                        byte[] buf = new byte[1024];
                        count = sstream.Read(buf, 0, 1024);
                        ms.Write(buf, 0, count);
                    } while (sstream.CanRead && count > 0);
                    audioByte = ms.ToArray();
                }

                if(audioByte.Length == 0)
                {
                    return null;
                }

                CloudStorageAccount storageAccount = CloudStorageAccount.Parse(ConnectString);
                CloudBlobClient blobClient = storageAccount.CreateCloudBlobClient();
                CloudBlobContainer container = blobClient.GetContainerReference(ContainerName);

                CloudBlockBlob blockBlob = container.GetBlockBlobReference(fileName);
                blockBlob.UploadFromByteArrayAsync(audioByte, 0, audioByte.Length).Wait();

                var storedPolicy = new SharedAccessBlobPolicy()
                {
                    SharedAccessExpiryTime = DateTime.UtcNow.AddMinutes(10),
                    Permissions = SharedAccessBlobPermissions.Read
                };

                return URLPrefix + fileName + blockBlob.GetSharedAccessSignature(storedPolicy);
            }
            catch (Exception ex)
            {
                LogHelper.WriteLog("SaveToBlob", ex);
            }
            return null;
        }

        public static string SaveToBlob(string fileName, string filePath)
        {
            try
            {
                CloudStorageAccount storageAccount = CloudStorageAccount.Parse(ConnectString);
                CloudBlobClient blobClient = storageAccount.CreateCloudBlobClient();
                CloudBlobContainer container = blobClient.GetContainerReference(ContainerName);

                CloudBlockBlob blockBlob = container.GetBlockBlobReference(fileName);
                blockBlob.UploadFromFileAsync(filePath).Wait();

                var storedPolicy = new SharedAccessBlobPolicy()
                {
                    SharedAccessExpiryTime = DateTime.UtcNow.AddMinutes(10),
                    Permissions = SharedAccessBlobPermissions.Read
                };

                return URLPrefix + fileName + blockBlob.GetSharedAccessSignature(storedPolicy);
            }
            catch (Exception ex)
            {
                LogHelper.WriteLog("SaveToBlob", ex);
            }
            return null;
        }

        public static void DeleteWithWechatId(string folderName, string id)
        {
            try
            {
                CloudStorageAccount storageAccount = CloudStorageAccount.Parse(ConnectString);
                CloudBlobClient blobClient = storageAccount.CreateCloudBlobClient();
                CloudBlobContainer container = blobClient.GetContainerReference(ContainerName);
                OperationContext context = new OperationContext();
                BlobRequestOptions options = new BlobRequestOptions();

                BlobResultSegment item = container.ListBlobsSegmentedAsync($"{folderName}/{id}", true, BlobListingDetails.All, null, null, options, context).Result;

                foreach (var blob in item.Results)
                {
                    var blobName = blob.Uri.ToString().Replace(URLPrefix, "");
                    CloudBlockBlob blockBlob = container.GetBlockBlobReference(blobName);
                    blockBlob.DeleteAsync().Wait();
                }
            }
            catch (Exception ex)
            {
                LogHelper.WriteLog("DeleteWithWechatId", ex);
            }

            return;
        }

        public static void DeleteFromBlob(string fileName)
        {
            try
            {
                if (fileName == null)
                {
                    return;
                }

                fileName = fileName.Replace(URLPrefix, "");
                CloudStorageAccount storageAccount = CloudStorageAccount.Parse(ConnectString);
                CloudBlobClient blobClient = storageAccount.CreateCloudBlobClient();
                CloudBlobContainer container = blobClient.GetContainerReference(ContainerName);

                CloudBlockBlob blockBlob = container.GetBlockBlobReference(fileName);
                blockBlob.DeleteAsync().Wait();
            }
            catch (Exception ex)
            {
                LogHelper.WriteLog("DeleteFromBlob", ex);
            }

            return;
        }

        public static void DeleteListFromBlob(List<string> fileNames)
        {
            try
            {
                CloudStorageAccount storageAccount = CloudStorageAccount.Parse(ConnectString);
                CloudBlobClient blobClient = storageAccount.CreateCloudBlobClient();
                CloudBlobContainer container = blobClient.GetContainerReference(ContainerName);

                foreach (var fileName in fileNames)
                {
                    if (fileName != null)
                    {
                        var blobName = fileName.Replace(URLPrefix, "");
                        CloudBlockBlob blockBlob = container.GetBlockBlobReference(blobName);
                        blockBlob.DeleteAsync().Wait();
                    }
                }
            }
            catch (Exception ex)
            {
                LogHelper.WriteLog("DeleteListFromBlob", ex);
            }

            return;
        }

        public static string GetBlobPath(string blobName, string folderName, string fileName)
        {
            return $"{blobName}/{folderName}/{fileName}";
        }

        public static string GetBlobPath(string blobName, string folderName, string subFolderName, string fileName)
        {
            return $"{blobName}/{folderName}/{subFolderName}/{fileName}";
        }
    }
}
