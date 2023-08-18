# SSML XSD Schema
This is the XSD schema of SSML. You can use it to validate your SSML locally.  
Please note the schema do **NOT** check the phoneme string in `<phoneme>` tag. 

## dotnet example
```csharp
XmlSchemaSet ssmlSchema = new();
ssmlSchema.Add(XmlSchema.Read(XElement.Load(@"xsd/ssml.xsd").CreateReader(), null)!);
ssmlSchema.Add(XmlSchema.Read(XElement.Load(@"xsd/xml.xsd").CreateReader(), null)!);
ssmlSchema.Add(XmlSchema.Read(XElement.Load(@"xsd/ssml_mstts.xsd").CreateReader(), null)!);
ssmlSchema.Add(XmlSchema.Read(XElement.Load(@"xsd/mathml.xsd").CreateReader(), null)!);
ssmlSchema.Compile();

using StreamWriter sw = new("ssml_log.txt");
foreach (var ssml in File.ReadAllLines("ssml.txt"))
{
    var ssmlDocument = XDocument.Parse(ssml);

    bool isValid = true;
    string error = string.Empty;
    ssmlDocument.Validate(
        ssmlSchema,
        (sender, args) =>
        {
            if (args.Severity == XmlSeverityType.Error)
            {
                isValid = false;
                if (sender is XElement element)
                {
                    error = $"{element.Name.LocalName}: {args.Message}";
                }
                else if (sender is XAttribute attr)
                {
                    error = $"{attr.Name.LocalName}: {args.Message}";
                }
            }
        });

    sw.WriteLine(isValid ? "Pass!" : error);
}
```

