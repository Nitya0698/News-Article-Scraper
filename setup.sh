echo "Installing Requirements"

pip3 install requirements.txt
echo "Initialising Database"

python3 Create_Articles_Database.py
python3 Create_Tracking_Domains_Database.py