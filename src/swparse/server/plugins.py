from advanced_alchemy.extensions.litestar import SQLAlchemyPlugin
from litestar.plugins.structlog import StructlogPlugin
from litestar_granian import GranianPlugin
from litestar_saq import SAQPlugin

from swparse.config import app as config
from swparse.server.builder import ApplicationConfigurator

structlog = StructlogPlugin(config=config.log)
saq = SAQPlugin(config=config.saq)
alchemy = SQLAlchemyPlugin(config=config.alchemy)
granian = GranianPlugin()
app_config = ApplicationConfigurator()
