import gspread
from oauth2client.service_account import ServiceAccountCredentials


def get_sheet(url):
    # connect to google drive each time as credentials time out after a while of not using them
    credentials = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json',
                                                                   ['https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(credentials)
    return gc.open_by_url(url).sheet1
