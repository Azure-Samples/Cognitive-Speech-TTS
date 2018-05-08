# How to run the sample

## Dependency

Ruby development files are necessary to build the native extension through gem. On Ubuntu 16.04, the commands are:

```sh
sudo apt install ruby2.3-dev
sudo gem install ruby_speech
```

## Usage

1. Get unified api key for [Free](https://azure.microsoft.com/en-us/try/cognitive-services/?api=speech-services) or [Paid](https://go.microsoft.com/fwlink/?LinkId=872236)
1. Fill the key to the line in code `apiKey = "Your api key goes here"`
1. Run `ruby TTSSample.rb` to get the result
