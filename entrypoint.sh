#!/bin/bash

# Apply database migrations
# because it can take some time to startup postgresql
# do 5 attempts with 1 sec interval
for i in 1 2 3 4 5; do
    echo "Apply database migrations: attempt $i"
    python manage migrate
    test $? -eq 0 && break
    sleep 1
done

# Start server
echo "Starting server"
python manage runserver 0.0.0.0:8000 2>&1 | tee heartface-django.log
