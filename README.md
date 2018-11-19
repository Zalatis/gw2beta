# GW2DiscordBot FR

Public Bot : https://discordapp.com/oauth2/authorize?client_id=336860774418874400&scope=bot&permissions=2288704

# Credits
https://github.com/Maselkov/GW2Bot-Red for guildwars2 cog

https://github.com/asmalic/anddy43-cogs for eventmaker cog

https://github.com/tekulvw/Squid-Plugins/tree/master/rss for rss cog

https://github.com/Sitryk/Sitryk-Cogs for genius cog

https://github.com/Redjumpman/Jumper-Cogs/tree/master/cookie for cookie cog

https://github.com/AznStevy/Maybe-Useful-Cogs/tree/master/leveler for leveler cog

# Donation

https://paypal.me/zalati

# Installation
echo "deb http://httpredir.debian.org/debian jessie-backports main contrib non-free" >> /etc/apt/sources.list

apt-get update

apt-get install build-essential libssl-dev libffi-dev git ffmpeg libopus-dev unzip -y

wget https://www.python.org/ftp/python/3.6.0/Python-3.6.0.tgz

tar xvf Python-3.6.0.tgz

cd Python-3.6.0

./configure --enable-optimizations

make -j4

make altinstall

cd ..

wget https://bootstrap.pypa.io/get-pip.py

python3.6 get-pip.py

npm install

git clone https://github.com/kurtmckee/feedparser.git

cd feedparser

python3.6 setup.py install

cd ..

git clone https://git.launchpad.net/pytz

cd pytz-2017.2

python3.6 setup.py install

service mongodb start

python3.6 launcher.py


