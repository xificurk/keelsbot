#Example setup.py for using py2exe with sleekxmpp

from distutils.core import setup
import py2exe

setup(
    version = "0.1.0",
    description = "A sleek XMPP client library example application",
    name = "sleekxmpp example",

    console = ["example.py"],
    options={"py2exe":{
        "includes":[
            "plugins.base", #sleekxmpp.plugins.base
            "plugins.xep_0004",
            "plugins.xep_0030",
            "plugins.xep_0078",
            "plugins.xep_0092",
            "dbhash", #only if tlslite is installed
            ],
        }},
    )
