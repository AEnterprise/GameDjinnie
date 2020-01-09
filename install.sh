#! /bin/sh

if [ $(whoami) != "root" ]; then
	echo "This installer needs to be ran by root (or with sudo) to work"
	exit
fi

echo "Installing requirements..."

python3 -m pip install -r requirements.txt

echo "Requirements installed, creating config, please answer the following questions. If you make a mistake you can terminate the script and start again or edit the values in config.yaml"

read -p "Bot token: " token
read -p "ID of the channel for the bot to use for startup and error logs: " channel
read -p "Prefix for the bot to use: " prefix
read -p "Userid of the bot admin: " admin_id
read -p "ID of the channel for test announcements: " announcement_channel
read -p "ID of the testers role: " tester_role
read -p "Emoji to use for the reaction (send the emoji with a \\ in front of it on discord. if you see a unicode emoji, copy and paste it here, if you see a text copy the number part and paste it here): " reaction_emoji

cat > config.yaml << EOL
token: "$token"
log_channel: $channel
prefix: "$prefix"
admin_id: $admin_id
emoji: {}
announcement_channel: $announcement_channel
tester_role: $tester_role
reaction_emoji: $reaction_emoji
EOL

echo "Config file created, creating service file"
dir=$(pwd)
user=$(who am i | awk '{print $1}')
cat > /etc/systemd/system/gamedjinnie.service << EOL
[Unit]
Description="gamedjinnie service"
After=network.target
[Service]
WorkingDirectory=$dir
ExecStart=$dir/bootloader.sh
Restart=always
User=$user
[Install]
WantedBy=multi-user.target
EOL

echo "Service file created, reloading deamon"
systemctl daemon-reload

echo "reloaded, configuring service to start with the system"
systemctl enable gamedjinnie
echo "done, starting service"
systemctl start gamedjinnie
echo "Gamedjinnie started, installer complete"
echo "Logs can be found by using journalctl or in the logs folder"