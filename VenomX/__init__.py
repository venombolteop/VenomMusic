
#
# All rights reserved.

from VenomX.core.bot import AyuBot
from VenomX.core.dir import dirr
from VenomX.core.git import git
from VenomX.core.userbot import Userbot
from VenomX.misc import dbb, heroku, sudo

from .logging import LOGGER

# Directories
dirr()

# Check Git Updates
git()

# Initialize Memory DB
dbb()

# Heroku APP
heroku()

# Load Sudo Users from DB
sudo()

# Bot Client
app = AyuBot()

# Assistant Client
userbot = Userbot()

from .platforms import PlaTForms

Platform = PlaTForms()
HELPABLE = {}
