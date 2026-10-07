
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

# Single source for the version. The startup banner reads this rather than
# carrying its own copy, so a hardcoded "v2.3.3" in the banner cannot outlive the
# release it described.
__version__ = "2.3.3"
