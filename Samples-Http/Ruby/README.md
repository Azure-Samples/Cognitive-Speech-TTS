# How to run the sample

## Dependency

Ruby development files are necessary to build the native extension through gem. On Ubuntu 16.04, the commands are:

```sh
sudo apt install ruby2.3-dev
sudo gem install ruby_speech
```

## Usage

1. Get api key for [Free](https://www.microsoft.com/cognitive-services/en-us/subscriptions?productId=/products/Bing.Speech.Preview) or [Paid](https://portal.azure.com/#create/Microsoft.CognitiveServices/apitype/Bing.Speech/pricingtier/S0)
1. Fill the key to the line in code `apiKey = "Your api key goes here"`
1. Run `ruby TTSSample.rb` to get the result
