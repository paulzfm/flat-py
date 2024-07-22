import smtplib
import ssl

from_address = "paulzfm@gmail.com"
password = 'zyburrhncuwbyshj'

data = f"""This is a test message\r\n.\r
MAIL FROM:{from_address}
RCPT TO:<fengmin.zhu@cispa.de>
DATA
test message
"""
context = ssl.create_default_context()
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(from_address, password)
    res = server.sendmail(from_address, "fengmin.zhu@cispa.de", data)
    print(res)
