namespace Microsoft.SpeechServices.CommonLib.Enums;

using System;
using System.Runtime.Serialization;

[DataContract]
public enum DeploymentEnvironment
{
    [EnumMember]
    Default,

    [EnumMember]
    Local,

    [EnumMember]
    Develop,

    [EnumMember]
    DevelopEUS,

    [EnumMember]
    CanaryUSCX,

    [EnumMember]
    ProductionAUE,

    [EnumMember]
    ProductionBRS,

    [EnumMember]
    ProductionCAC,

    [EnumMember]
    ProductionUSW,

    [EnumMember]
    ProductionUSW3,

    [EnumMember]
    ProductionUSWC,

    [EnumMember]
    ProductionEA,

    [EnumMember]
    ProductionEUS,

    [EnumMember]
    ProductionEUS2,

    [EnumMember]
    ProductionFC,

    [EnumMember]
    ProductionGWC,

    [EnumMember]
    ProductionINC,

    [EnumMember]
    ProductionJINW,

    [EnumMember]
    ProductionJPE,

    [EnumMember]
    ProductionJPW,

    [EnumMember]
    ProductionKC,

    [EnumMember]
    ProductionNEU,

    [EnumMember]
    ProductionNOE,

    [EnumMember]
    ProductionQAC,

    [EnumMember]
    ProductionSAN,

    [EnumMember]
    ProductionSEA,

    [EnumMember]
    ProductionSEC,

    [EnumMember]
    ProductionSWN,

    [EnumMember]
    ProductionSWW,

    [EnumMember]
    ProductionUAEN,

    [EnumMember]
    ProductionUKS,

    [EnumMember]
    ProductionUSC,

    [EnumMember]
    ProductionUSNC,

    [EnumMember]
    ProductionUSSC,

    [EnumMember]
    ProductionWEU,

    [EnumMember]
    ProductionWUS2,

    [EnumMember]
    MooncakeChinaEast2,

    [EnumMember]
    DevelopWEU,

    [EnumMember]
    CanaryUSE2X,

    [EnumMember]
    Internal,

    [EnumMember]
    FairfaxDevOps,

    [EnumMember]
    FairfaxVirginia,

    [EnumMember]
    FairfaxArizona,

    [EnumMember]
    MooncakeDevOps,
}