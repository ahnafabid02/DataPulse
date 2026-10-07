"""Hospital registry migrations use only the caller's explicit local connection."""

from alembic import context

connection = context.config.attributes["connection"]
context.configure(connection=connection)
with context.begin_transaction():
    context.run_migrations()
