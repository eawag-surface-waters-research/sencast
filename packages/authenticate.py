__author__ = 'Daniel'

from http.cookiejar import CookieJar
import urllib.request


def authenticate(username, password):

    # See discussion https://github.com/SciTools/cartopy/issues/789#issuecomment-245789751
    # And the solution on https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python

    # Create a password manager to deal with the 401 reponse that is returned from
    # Earthdata Login

    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, "https://urs.earthdata.nasa.gov", username, password)

    # Create a cookie jar for storing cookies. This is used to store and return
    # the session cookie given to use by the data server (otherwise it will just
    # keep sending us back to Earthdata Login to authenticate).  Ideally, we
    # should use a file based cookie jar to preserve cookies between runs. This
    # will make it much more efficient.

    cookie_jar = CookieJar()

    # Install all the handlers.

    opener = urllib.request.build_opener(
        urllib.request.HTTPBasicAuthHandler(password_manager),
        #urllib2.HTTPHandler(debuglevel=1),    # Uncomment these two lines to see
        #urllib2.HTTPSHandler(debuglevel=1),   # details of the requests/responses
        urllib.request.HTTPCookieProcessor(cookie_jar))
    urllib.request.install_opener(opener)

    return