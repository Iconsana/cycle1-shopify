import json

# Paste your JSON content between the triple quotes here
json_content = '''
  "project_id": "cycle2-444100",
{
  "type": "service_account",
  "private_key_id": "2182dd168025ece20cb8df079075ac4a1e697aab",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCjCxr6rhBPVroI\nrOqR7XwqVZQU/4m1A8ibgTdbVC6qEczrvEAggXqFSVDsUbGXyTc0xGij+DKmpf0o\nvLtbvWjS3t+wE3up4PC206E4E1JQbBzoGb9Vv+9BoLjb/PGJZ9x84qJif0bRchzV\nDH0VXd+YExwrFw3b428I0DNydcTrHasPYvX3/jtoKNvO9F6OKNhqpOdz/ujuCPI/\nvVLXMitmCnt+vkskvZC2nUs+tuNPCTQ9V64qySi4hCDGcBpOVwS/VU63RBj8HPQV\nTnjxRAKLc9g7U3MgRhZGjkEo8jY4zcyXUzxMKBrY6XABojeut62w3bKwQVwY7V56\n1sgaYCXfAgMBAAECggEAGlBesdT+9+G+PkveGIrfeRunvdMs6qSU2hglkt1dd1Wj\ny5YYiXEsO4UaL5HTG6ATg2DW/JkVtP9hgj4iRPZRtoWBokglXhpaRJTtAQEJThvX\ndymUpPvIWxYGpSadOvkixPB07HhbOc7KKCO5r7BKDSAPHJs+Ft44MOVysDH2rqAF\nw09TDmf5QcCoriRmuiG9gQBlGUPwtRMkFjv+FMr6WPyRWVJtMum0sFuIieZiVuq3\nMOOOYtcSXFpQEdpkJyQtQbxRS0b7Ne0UwRv6UfZTpFFQa+Zo3DoOvwl632cGZYL+\nxBKZ5+EhNx1Auzosug0g/z2hRTA611swy2JB1p636QKBgQDgze/rp1vyVYIQ0GBx\nQb8alhN6SIE/7hiGnQEiG1lFxyQyi2l8PBuxP2xyqRkmayVXb6ubi0pbaIqwWwmI\negWxUYgTAsI3XDZApEKJfxYH+Ayqj+UagfOMsJ2ETtrXJoBQoCXM6ud4yK7A1dWs\n9XE+5iFu7Vm/aU0UPnTd9da9GQKBgQC5qyNYybJu2jhV9ALffF06sj0LRMIHzYgm\nUSovi4IcAHjnM3NfR6n6fabUmsoXnsjxKeqM5TzNrFlrF0FtBASbz3J8sjaniRIT\nmY+dKDD3Iq2ixmzzxNwXnoLIARrn5g/jhVNMGrhFR23di2+J5C23Wx2lQHAjCg5e\nuNNM+IzhtwKBgBeMWvJzcIU9AcfjHAchHPSa/eVUTP22YilPrvu0o7BUgO0uf1k9\nLqVtgF2uau0EUkALeY1slNhoZga9Mo1yQsBlSvy60D9eUGyLCFFA17zz9de0BQq2\nzB1TrtxaKkBZTx2i+PKzNJYJZ4zZmW1ptHgjQSNOh5UuYZ2aQUGy69CZAoGADpiF\njtVMUaqWAyvLjgYYziR06A3fsv1VVq3KwzIUaF8hIgvJZhQcKLT4CH6ipHi3Ez5Y\nUfszbHfAD8skOY23Twhf162q3kDISwInaBNgxgzT2Zf/uKohIzoyzcZIdzJ+zUQN\n6E2xbsDOwjvT6OMnNOLU0cjfB+Iifw/IjKR9bsECgYEA3iFrmshmLKtM4Q7tFiMI\n7JwJXJPrtTQvF5yC0jTGFM7IX1xhAip/pguCrcpIKW6X/6R47Sc8uMC41pfiVXIk\nvZFFHfG9mS09B60RYpDtMpP506KbEdZGLIlubP2NJMUG+zTnGUraWwKuO0sibzHB\nv63nmRjhIPwkapQE48XiqN8=\n-----END PRIVATE KEY-----\n",
  "client_email": "acdc-stock-sync@cycle2-444100.iam.gserviceaccount.com",
  "client_id": "117749978795451170732",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/acdc-stock-sync%40cycle2-444100.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}'''

# Convert to single line
single_line = json.dumps(json_content)
print("Here's your environment variable value:")
print(single_line)
