from .base import *

# If set to False, test db will not be migrated (but initialized using syncdb). Makes running
#  tests faster, but may break them if tests rely on migrations. (E.g. migrations adding data.)
SOUTH_TESTS_MIGRATE = False

# Skip South's own tests. The documentation suggests that these are fragile caused by
#  some mocking with INSTALLED_APPS, and we don't want to run South tests anyway.
SKIP_SOUTH_TESTS = True
