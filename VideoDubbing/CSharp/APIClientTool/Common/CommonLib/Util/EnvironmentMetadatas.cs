namespace Microsoft.SpeechServices.CommonLib.Util;

using Microsoft.SpeechServices.CommonLib.Enums;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

public class EnvironmentMetadatas
{
    public static ReadOnlyDictionary<DeploymentEnvironment, DcMetadata> DcMetadatas => new ReadOnlyDictionary<DeploymentEnvironment, DcMetadata>(new Dictionary<DeploymentEnvironment, DcMetadata>()
    {
        {
            DeploymentEnvironment.Local,
            new DcMetadata()
            {
                Environment = DeploymentEnvironment.Local,
                ApiHostName = "localhost",
                ApiPort = 44311,
            }
        },
        {
            DeploymentEnvironment.Develop,
            new DcMetadata()
            {
                Environment = DeploymentEnvironment.Develop,
                ApiHostName = "develop.customvoice.api.speech-test.microsoft.com",
            }
        },
        {
            DeploymentEnvironment.DevelopEUS,
            new DcMetadata()
            {
                Environment = DeploymentEnvironment.DevelopEUS,
                ApiHostName = "developeus.customvoice.api.speech-test.microsoft.com",
            }
        },
        {
            DeploymentEnvironment.CanaryUSCX,
            new DcMetadata()
            {
                RegionIdentifier = "centraluseuap",
                Environment = DeploymentEnvironment.CanaryUSCX,
            }
        },
        {
            DeploymentEnvironment.ProductionAUE,
            new DcMetadata()
            {
                RegionIdentifier = "australiaeast",
                Environment = DeploymentEnvironment.ProductionAUE,
            }
        },
        {
            DeploymentEnvironment.ProductionBRS,
            new DcMetadata()
            {
                RegionIdentifier = "brazilsouth",
                Environment = DeploymentEnvironment.ProductionBRS,
            }
        },
        {
            DeploymentEnvironment.ProductionCAC,
            new DcMetadata()
            {
                RegionIdentifier = "canadacentral",
                Environment = DeploymentEnvironment.ProductionCAC,
            }
        },
        {
            DeploymentEnvironment.ProductionEA,
            new DcMetadata()
            {
                RegionIdentifier = "eastasia",
                Environment = DeploymentEnvironment.ProductionEA,
            }
        },
        {
            DeploymentEnvironment.ProductionEUS,
            new DcMetadata()
            {
                RegionIdentifier = "eastus",
                Environment = DeploymentEnvironment.ProductionEUS,
            }
        },
        {
            DeploymentEnvironment.ProductionEUS2,
            new DcMetadata()
            {
                RegionIdentifier = "eastus2",
                Environment = DeploymentEnvironment.ProductionEUS2,
            }
        },
        {
            DeploymentEnvironment.ProductionFC,
            new DcMetadata()
            {
                RegionIdentifier = "francecentral",
                Environment = DeploymentEnvironment.ProductionFC,
            }
        },
        {
            DeploymentEnvironment.ProductionGWC,
            new DcMetadata()
            {
                RegionIdentifier = "germanywestcentral",
                Environment = DeploymentEnvironment.ProductionGWC,
            }
        },
        {
            DeploymentEnvironment.ProductionINC,
            new DcMetadata()
            {
                RegionIdentifier = "centralindia",
                Environment = DeploymentEnvironment.ProductionINC,
            }
        },
        {
            DeploymentEnvironment.ProductionJINW,
            new DcMetadata()
            {
                RegionIdentifier = "jioindiawest",
                Environment = DeploymentEnvironment.ProductionJINW,
            }
        },
        {
            DeploymentEnvironment.ProductionJPE,
            new DcMetadata()
            {
                RegionIdentifier = "japaneast",
                Environment = DeploymentEnvironment.ProductionJPE,
            }
        },
        {
            DeploymentEnvironment.ProductionJPW,
            new DcMetadata()
            {
                RegionIdentifier = "japanwest",
                Environment = DeploymentEnvironment.ProductionJPW,
            }
        },
        {
            DeploymentEnvironment.ProductionKC,
            new DcMetadata()
            {
                RegionIdentifier = "koreacentral",
                Environment = DeploymentEnvironment.ProductionKC,
            }
        },
        {
            DeploymentEnvironment.ProductionNEU,
            new DcMetadata()
            {
                RegionIdentifier = "northeurope",
                Environment = DeploymentEnvironment.ProductionNEU,
            }
        },
        {
            DeploymentEnvironment.ProductionNOE,
            new DcMetadata()
            {
                RegionIdentifier = "norwayeast",
                Environment = DeploymentEnvironment.ProductionNOE,
            }
        },
        {
            DeploymentEnvironment.ProductionQAC,
            new DcMetadata()
            {
                RegionIdentifier = "qatarcentral",
                Environment = DeploymentEnvironment.ProductionQAC,
            }
        },
        {
            DeploymentEnvironment.ProductionUAEN,
            new DcMetadata()
            {
                RegionIdentifier = "uaenorth",
                Environment = DeploymentEnvironment.ProductionUAEN,
            }
        },
        {
            DeploymentEnvironment.ProductionUSW3,
            new DcMetadata()
            {
                RegionIdentifier = "westus3",
                Environment = DeploymentEnvironment.ProductionUSW3,
            }
        },
        {
            DeploymentEnvironment.ProductionSAN,
            new DcMetadata()
            {
                RegionIdentifier = "southafricanorth",
                Environment = DeploymentEnvironment.ProductionSAN,
            }
        },
        {
            DeploymentEnvironment.ProductionSEA,
            new DcMetadata()
            {
                RegionIdentifier = "southeastasia",
                Environment = DeploymentEnvironment.ProductionSEA,
            }
        },
        {
            DeploymentEnvironment.ProductionSWN,
            new DcMetadata()
            {
                RegionIdentifier = "switzerlandnorth",
                Environment = DeploymentEnvironment.ProductionSWN,
            }
        },
        {
            DeploymentEnvironment.ProductionSWW,
            new DcMetadata()
            {
                RegionIdentifier = "switzerlandwest",
                Environment = DeploymentEnvironment.ProductionSWW,
            }
        },
        {
            DeploymentEnvironment.ProductionUKS,
            new DcMetadata()
            {
                RegionIdentifier = "uksouth",
                Environment = DeploymentEnvironment.ProductionUKS,
            }
        },
        {
            DeploymentEnvironment.ProductionUSC,
            new DcMetadata()
            {
                RegionIdentifier = "centralus",
                Environment = DeploymentEnvironment.ProductionUSC,
            }
        },
        {
            DeploymentEnvironment.ProductionUSNC,
            new DcMetadata()
            {
                RegionIdentifier = "northcentralus",
                Environment = DeploymentEnvironment.ProductionUSNC,
            }
        },
        {
            DeploymentEnvironment.ProductionUSSC,
            new DcMetadata()
            {
                RegionIdentifier = "southcentralus",
                Environment = DeploymentEnvironment.ProductionUSSC,
            }
        },
        {
            DeploymentEnvironment.ProductionUSW,
            new DcMetadata()
            {
                RegionIdentifier = "westus",
                Environment = DeploymentEnvironment.ProductionUSW,
            }
        },
        {
            DeploymentEnvironment.ProductionUSWC,
            new DcMetadata()
            {
                RegionIdentifier = "westcentralus",
                Environment = DeploymentEnvironment.ProductionUSWC,
            }
        },
        {
            DeploymentEnvironment.ProductionWEU,
            new DcMetadata()
            {
                RegionIdentifier = "westeurope",
                Environment = DeploymentEnvironment.ProductionWEU,
            }
        },
        {
            DeploymentEnvironment.ProductionWUS2,
            new DcMetadata()
            {
                RegionIdentifier = "westus2",
                Environment = DeploymentEnvironment.ProductionWUS2,
            }
        },
        {
            DeploymentEnvironment.MooncakeChinaEast2,
            new DcMetadata()
            {
                Environment = DeploymentEnvironment.MooncakeChinaEast2,
                RegionIdentifier = "chinaeast2",
            }
        }
    });

    public class DcMetadata
    {
        private string apiHostName = null;

        public DeploymentEnvironment Environment { get; set; }

        public string PortalAddress
        {
            get
            {
                var address = ApiHostName;
                if (!string.IsNullOrEmpty(address) && ApiPort != null)
                {
                    address = $"{address}:{ApiPort.Value}";
                }

                return address;
            }
        }

        public int? ApiPort { get; set; }

        public string RegionIdentifier { get; set; }

        public string ApiHostName
        {
            get
            {
                if (!string.IsNullOrEmpty(apiHostName))
                {
                    return apiHostName;
                }
                else if (!string.IsNullOrEmpty(RegionIdentifier))
                {
                    return $"{RegionIdentifier}.customvoice.api.speech.microsoft.com";
                }

                return string.Empty;
            }
            set
            {
                apiHostName = value;
            }
        }

        public static Uri GetApiBaseUrl(DeploymentEnvironment environment)
        {
            Uri url = null;
            if (!string.IsNullOrEmpty(DcMetadatas[environment].PortalAddress))
            {
                url = new Uri($"https://{DcMetadatas[environment].PortalAddress}/");
            }

            return url;
        }
    }
}
