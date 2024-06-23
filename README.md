# Summary

The project defines a voice assistant solution for controlling a VoIP telephone.

# Funding

The project was funded by the German Federal Ministry of Education and Research under grant number 01IS22S34 from September 2022 to February 2023. The authors are responsible for the content of this publication.

<img src="BMBF_gefoerdert_2017_en.jpg" width="300px"/>

# Installation

Ubuntu 20.04 is used as reference OS with the `apt` package manager. 
On other OS a different package manager providing the same packages should work.  

## Prerequisites

### Python

Install Python 3.10:

~~~shell
sudo apt install python3.10
~~~

FFmpeg:

~~~shell
sudo apt-get install ffmpeg
~~~

### aarch64

In an aarch64 environment install the following dependencies:

~~~shell
# aarch64 architecture
sudo apt install python3.10-dev portaudio19-dev
~~~

### Xavier NX

The Xavier NX needs a special PyTorch version. The [NVIDIA instructions](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html) 
must be followed summarized here:

~~~shell
sudo apt-get -y install autoconf bc build-essential g++-8 gcc-8 clang-8 lld-8 gettext-base gfortran-8 iputils-ping libbz2-dev libc++-dev libcgal-dev libffi-dev libfreetype6-dev libhdf5-dev libjpeg-dev liblzma-dev libncurses5-dev libncursesw5-dev libpng-dev libreadline-dev libssl-dev libsqlite3-dev libxml2-dev libxslt-dev locales moreutils openssl python-openssl rsync scons python3-pip libopenblas-dev
export TORCH_INSTALL=https://developer.download.nvidia.cn/compute/redist/jp/v502/pytorch/torch-1.13.0a0+410ce96a.nv22.12-cp38-cp38-linux_aarch64.whl
python3 -m pip install --upgrade pip; python3 -m pip install aiohttp; export "LD_LIBRARY_PATH=/usr/lib/llvm-8/lib:$LD_LIBRARY_PATH"; python3 -m pip install --upgrade protobuf; python3 -m pip install --no-cache $TORCH_INSTALL
~~~

__NOTE:__ Do not install `numpy=='1.19.4' scipy=='1.5.3'` like given in the original NVIDIA instructions. This would be incompatible with Coqui TTS.

Take a recent PyTorch version as `TORCH_INSTALL` matching the JetPack version running (here 502) from [PyTorch Wheel downloads](https://developer.download.nvidia.cn/compute/redist/jp/v502/pytorch/).

### WiFi

Needed, if no ethernet cable should be used.

Instructions taken from: https://www.linuxbabe.com/ubuntu/connect-to-wi-fi-from-terminal-on-ubuntu-18-04-19-04-with-wpa-supplicant

__NOTE:__ Replace `wlp3s0` with the interface report by `iwconfig`. 

~~~shell
sudo apt install wireless-tools
sudo apt install net-tools
iwconfig
sudo ifconfig wlp3s0 up
sudo iw dev wlp3s0 scan ap-force | grep SSID
sudo apt install wpasupplicant
wpa_passphrase 'your-ESSID' your-wifi-passphrase | sudo tee /etc/wpa_supplicant.conf
# test connection
sudo wpa_supplicant -c /etc/wpa_supplicant.conf -i wlp3s0
# different terminal
sudo dhclient wlp3s0
ip addr show wlp3s0
# CTRL+C to abort wpa_supplicant
sudo cp /lib/systemd/system/wpa_supplicant.service /etc/systemd/system/wpa_supplicant.service
sudo nano /etc/systemd/system/wpa_supplicant.service
# change line to ExecStart=/sbin/wpa_supplicant -u -s -c /etc/wpa_supplicant.conf -i wlp3s0
# comment out Alias=dbus-fi.w1.wpa_supplicant1.service
sudo systemctl daemon-reload
sudo systemctl enable wpa_supplicant.service
sudo nano /etc/systemd/system/dhclient.service
~~~

Use the following content:

~~~
[Unit]
Description= DHCP Client
Before=network.target
After=wpa_supplicant.service

[Service]
Type=forking
ExecStart=/sbin/dhclient wlp3s0 -v
ExecStop=/sbin/dhclient wlp3s0 -r
Restart=always
 
[Install]
WantedBy=multi-user.target
~~~

~~~shell
sudo systemctl enable dhclient.service
sudo systemctl restart wpa_supplicant.service
# check status
sudo journalctl -u wpa_supplicant.service
sudo systemctl restart dhclient.service
ifconfig
~~~

### Time Daemon

~~~shell
timedatectl set-ntp true
sudo nano /etc/systemd/timesyncd.conf
~~~

Use:

~~~
[Time]
NTP=de.pool.ntp.org
~~~

Restart and check time:

~~~shell
sudo timedatectl set-timezone Europe/Berlin
systemctl restart systemd-timesyncd
journalctl -u systemd-timesyncd
~~~

### Hardware

#### MeLe Quieter2A

Add the WiFi driver: 

~~~shell
sudo apt install rtl8821ce-dkms
sudo reboot
~~~

#### Seed reComputer J2012

This [mini PC](https://www.seeedstudio.com/Jetson-20-1-H2-p-5329.html) is equipped with an NVIDIA Xavier NX 16 GB module 
to support offline speech recognition with OpenAID Whisper. 

The [WiFi Intel Wireless-AC 8265 M.2 key A+E module](https://wiki.seeedstudio.com/reComputer_Jetson_Series_Hardware_Layout/) (or a compatible WiFi module) must be added to have WiFi support.  
2 IPEX MHF2 cable and two SMA antennas.

##### Add M.2 SSD Disk

More disk space is need to run all necessary tools. A 64 GB or larger M.2 SSD has to be used 
and the [instructions](https://wiki.seeedstudio.com/reComputer_Jetson_Memory_Expansion/) have to be followed to boot from the SSD.

##### Flash latest JetPack version

To get the latest JetPack version (here 502) following the [instruction](https://wiki.seeedstudio.com/reComputer_J2021_J202_Flash_Jetpack/) to update the system.

##### WiFi after sleep not working 

The system has issues with resuming the network (LAN and WiFi) when resumed.

This script restarts the WiFi after the sleep mode:

~~~shell
sudo -i
cat <<'EOT' > /lib/systemd/system-sleep/restorenetwork.sleep
#!/bin/sh

PATH=/sbin:/usr/sbin:/bin:/usr/bin

case "$1" in
    pre)
    ;;
    post)
            modprobe -r iwlmvm
            modprobe -r iwlwifi
            modprobe iwlmvm
    ;;
esac

exit 0
EOT
chmod +x /lib/systemd/system-sleep/restorenetwork.sleep
exit
~~~

### Telephone NLU

Install [Telephone NLU](https://github.com/kaoh/TelephoneNLU).

## Program

Install the program:

~~~shell
pip install git+https://github.com/kaoh/HandsFreeTelephone.git
~~~

If the [Whisper](https://github.com/openai/whisper) installation fails try:

~~~shell
pip install setuptools-rust
~~~

Download speech models:

~~~shell
hands-free-telephone-setup
~~~

## Configuration

### Microphone Intensity

Each microphone has a different intensity which can be considered as silence. This must be measured with:

~~~shell
audio-intensity
~~~

While using the program read something while the program is running. The output can be used with the `--mic_threshold` option of the 
`hands-free-telephone` binary.

Some recorded values:

| Speaker                 | Value |
|-------------------------|-------|
| ReSpeaker USB Mic Array | 0.010 |
| Jabra UC 750            | 0.015 |
| Epos 40+                | 0.010 |
| Logitech P510e          | 0.025 |


### Cloud Credentials

Create a directory `hands_free_telephone`.
If installed as system service with `sudo mkdir /home/hands-free-user/hands_free_telephone`.
If locally installed in the user directory with `mkdir ~/hands_free_telephone`.

Place there:

* The MS Azure cloud configuration `ms-azure.json`. See below how to create it.
* The Google cloud API configuration `google-cloud.json`. Download it from the Google console.
* The IBM clod API configuration `ibm-sst-cloud.json` and `ibm-tts-cloud.json`. Download it from the IBM console.

#### MS Azure Configuration

Look up the API key and insert it into the `ms-azure.json` file:

~~~json
{
  "api-key": "API-KEY"
}
~~~

## Run as System Service

To run the program at system start execute the following scripts or adjust them to support your OS. 

~~~shell
sudo -i
# execute the following scripts
exit
~~~

Create dedicated system user:

~~~shell
adduser --shell=/bin/false --gecos "Hands-Free User" --disabled-login handsfree
usermod -a -G audio handsfree
~~~

Create Systemd scripts:

~~~shell
mkdir -p /lib/systemd/system/
cp hands_free_telephone.service /lib/systemd/system/
~~~

Enable and restart services:

~~~shell
/bin/systemctl enable hands_free_telephone
/bin/systemctl restart hands_free_telephone
~~~

In case of instabilities a Cron job can be created to restart the server every day:

~~~shell
mkdir -p /etc/cron.d
cat <<EOT > /etc/cron.d/hands_free_telephone
30 3 * * * root /bin/systemctl restart hands_free_telephone
EOT
~~~

# Execution

Start the Rasa server and the Rasa action server of the `telephone_nlu` project. Then:

~~~shell
hands-free-telephone 
~~~~

__NOTE:__ When running under aarch64 the bundled version `libgomp` of `scikit` must be preloaded. Export first `LD_PRELOAD` (or add `LD_PRELOAD` as environment variable to the starter):

~~~shell
export LD_PRELOAD=</usr | <virtual env directory>>/lib/python3.8/site-packages/sklearn/__check_build/../../scikit_learn.libs/libgomp-d22c30c5.so.1.0.0
~~~

To get a help screen type: 

~~~shell
hands-free-telephone --help 
~~~~

# Development

## Build Project

Checkout the project:

~~~shell
git clone <URL>
git pull --recurse-submodules
git submodule init
git submodule update
~~~

~~~shell
cd <project directory>
pyenv install 3.8.16
pyenv local 3.8.16
python3 -m venv venv
source venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
~~~

Install the prerequisites from the installation section.

## Test Packaging

Test the `pyproject.toml` package:

~~~shell
python3 -m venv testbuild
source testbuild/bin/activate
pip install -U pip
pip install .
~~~

To clean the build run (Otherwise old artifacts are retained):

~~~shell
rm -rf dist build *.egg-info
~~~

## Profiling

~~~shell
pip install line_profiler
export PYTHONPATH=$PYTHONPATH:speech_recognition && kernprof -l -v hands_free_telephone/hands_free_telephone.py
~~~

## Vosk (Keyword Recognition)

[Vosk](https://alphacephei.com/vosk/) is used a keyword offline recognizer.  
The[vosk-model-small-de-0.15 model](https://alphacephei.com/vosk/models) is downloaded in the vosk folder.

## Coqui STT  (Offline Recognition)

This does only work on x86_64 since no aarch64 wheels are provided.

The German speech model is using the [German model from Coqui](https://coqui.ai/models).

### External Scorer

These steps have to be executed to improve the scorer by providing a target vocabulary.  

A language model matching the corpus of telephone related commands is created according to the [Coqui documentation](https://stt.readthedocs.io/en/latest/LANGUAGE_MODEL.html).

Download the `alphabet.txt` and the checkpoints of the [German Coqui model](https://coqui.ai/models) and place it into the `coqui` folder.

The links to the checkpoint files are linked from [Jaco-Assistant](https://gitlab.com/Jaco-Assistant/Scribosermo/-/tree/master). 
Look at the Mozilla's DeepSpeech German link, which should direct to the [DeepSpeech model d17s5_de](https://drive.google.com/drive/folders/1oO-N-VH_0P89fcRKWEUlVDm-_z18Kbkb).
Download the `d17s5_de.tar.gz` file and extract it to under the `coqui` folder in the `d17s5` directory. 
Also place again the `alphabet.txt` in the `d17s5` directory.

 __NOTE:__ PyCharm is by default removing trailing whitespaces. Disable this under "Settings | Editor | General | Remove trailing spaces on Save"
The space must be included in `alphabet.txt` as a possible character otherwise rubbish will be created for the scorer. 
 Pay attention to this when editing the file.

#### Virtual Environment

For the scorer a separate virtual environment was set up. 
Since TensorFlow 1.15.4 is not available for python 3.8 a Python 3.7 environment is needed.

~~~shell
git clone https://github.com/pyenv/pyenv.git $HOME/.pyenv
~~~

Add to your `~/.bashrc`:

~~~shell
## pyenv configs
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"

if command -v pyenv 1>/dev/null 2>&1; then
  eval "$(pyenv init -)"
fi
~~~

Log out or run:

~~~shell
source ~/.bashrc
~~~

~~~shell
pyenv install 3.7.9
pyenv local 3.7.9
python3 -m venv coqui-stt-train-venv
source coqui-stt-train-venv/bin/activate
~~~

#### Coqui Tools 

~~~shell
git clone https://github.com/coqui-ai/STT
cd STT
python -m pip install --upgrade pip wheel setuptools
python -m pip install --upgrade -e .
~~~

#### Language Corpus

Defined in `coqui/data/corpus.txt`. Execute:

~~~shell
cd coqui
python3 create_input.py
~~~

This will create `input.txt` based on the corpus and several placeholder files.

#### Build KenML

~~~shell
cd STT
git submodule init
git pull --recurse-submodules
cd kenlm
sudo apt install build-essential cmake libboost-system-dev libboost-thread-dev libboost-program-options-dev libboost-test-dev libeigen3-dev zlib1g-dev libbz2-dev liblzma-dev
mkdir -p build
cd build
cmake ..
make -j 4
~~~

#### Execute generate_lm.py

~~~shell
cd coqui
python3 ../STT/data/lm/generate_lm.py --input_txt input.txt --output_dir . \
  --top_k 10000 --kenlm_bins ../STT/kenlm/build/bin/ \
  --arpa_order 3 --max_arpa_memory "85%" --arpa_prune "0|0|0" \
  --binary_a_bits 255 --binary_q_bits 8 --binary_type trie --discount_fallback
~~~

#### Create Scorer

~~~shell
# Download and extract appropriate native_client package:
curl -LO https://github.com/coqui-ai/STT/releases/download/v1.4.0/native_client.tflite.Linux.tar.xz
tar xvf native_client.tflite.Linux.tar.xz
./generate_scorer_package --checkpoint d17s5 --lm lm.binary --vocab vocab-10000.txt   --package kenlm.scorer --default_alpha 0.931289039105002 --default_beta 1.1834137581510284
~~~

#### Optimize scorer's alpha and beta values:

__NOTE:__ This step did not improve the recognition after several training epochs.

~~~shell
cp -R STT/training/coqui_stt_training .
cp STT/lm_optimizer.py .
python3 lm_optimizer.py --test_files training/train.csv --checkpoint_dir d17s5 kenlm.scorer
~~~

## IBM Speech To Text Customizations

Create a [custom speech corpus](https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-languageCreate):

~~~shell
export API_KEY=
curl -X POST -u "apikey:${API_KEY}" --header "Content-Type: application/json" --data "{\"name\": \"Telefon model\",   \"base_model_name\": \"de-DE_BroadbandModel\",   \"description\": \"Telefon custom language model\"}" ""https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations"
# response:
#{"customization_id": "7e76cde1-e1ea-404a-97ff-a6e643ad2409"}
~~~

Use the `input.txt` creates with `python3 create_input.py` in the `deepspeech` directory and then create some samples.

Not all lines of the `input.txt` corpus are needed:

~~~shell
cat input.txt | while read -r line; do random=$RANDOM; if [ $random -lt $((32767 / 100)) ]; then echo "$line" >> input_sample.txt; fi; done;
~~~

Import to IBM Speech To Text:

~~~shell
curl -X POST -u "apikey:${API_KEY}" --data-binary @deepspeech/input_sample.txt "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations/7e76cde1-e1ea-404a-97ff-a6e643ad2409/corpora/telephone?allow_overwrite=true"
~~~

Inspect the result:

~~~shell
curl -X GET -u "apikey:${API_KEY}" "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations/7e76cde1-e1ea-404a-97ff-a6e643ad2409/corpora/telephone"
#response:
#{
#   "out_of_vocabulary_words": 131,
#   "total_words": 3374880,
#   "name": "telephone",
#   "status": "analyzed"
#}
~~~

Add grammar ([Specification](https://www.w3.org/TR/speech-grammar/)):

~~~shell
curl -X POST -u "apikey:${API_KEY}" --header "Content-Type: application/srgs" --data-binary @deepspeech/grammar.txt "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations/7e76cde1-e1ea-404a-97ff-a6e643ad2409/grammars/telephone-abnf?allow_overwrite=true"
~~~

Query status:

~~~shell
curl -X GET -u "apikey:${API_KEY}" "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations/7e76cde1-e1ea-404a-97ff-a6e643ad2409/grammars/telephone-abnf"
~~~

Train the model:

~~~shell
curl -X POST -u "apikey:${API_KEY}" "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations/7e76cde1-e1ea-404a-97ff-a6e643ad2409/train"
~~~

Inspect the result:

~~~shell
curl -X GET -u "apikey:${API_KEY}" "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations/7e76cde1-e1ea-404a-97ff-a6e643ad2409"
~~~

__NOTE:__ If there are any words not working it might help to correct the word, e.g. fix the `sounds_like` parameter.

Check word:

~~~shell
curl -X GET -u "apikey:${API_KEY}" "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations/7e76cde1-e1ea-404a-97ff-a6e643ad2409/words/Katja"
~~~

Set `sounds_like`:

~~~shell
curl -X PUT -u "apikey:${API_KEY}" --header "Content-Type: application/json" --data "{\"sounds_like\":[\"katja\"]}" "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/customizations/7e76cde1-e1ea-404a-97ff-a6e643ad2409/words/Katja"
~~~

Test recognition:

~~~shell
curl -X POST -u "apikey:${API_KEY}" --header "Content-Type: audio/wav" --data-binary @.config/log/2021-11-03_22:15:00:049934.wav "https://api.eu-de.speech-to-text.watson.cloud.ibm.com/v1/recognize?model=de-DE_BroadbandModel&language_customization_id=7e76cde1-e1ea-404a-97ff-a6e643ad2409&grammar_name=telephone-abnf"
~~~

## audiotorch Compilation

This is necessary for an aarch64 computer, e.g. a Raspberry Pi 4 or Xavier NX.

For aarch64 a wheel must be created manually and placed in the `prebuilt` folder. 

~~~shell
git clone https://github.com/pytorch/audio.git
cd audio 
python setup.py install
cd dist
wheel convert torchaudio-2.0.0a0+c6a5235-py3.8-linux-aarch64.egg
~~~