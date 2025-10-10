# The port must be changed in src/config.yml on the server
PORT := 9201
# The service name, also the name of the directory in /srv
SERVICE_NAME := breaking-books

run:
	uv run --frozen streamlit run --server.port $(PORT) src/simple_web.py

deploy:
	git ls-files | rsync -avzP --files-from=- . pine:/srv/$(SERVICE_NAME)
	rsync -avzP .env.prod pine:/srv/$(SERVICE_NAME)/
	rsync -avzP $(SERVICE_NAME).service pine:/etc/systemd/system/
	ssh pine "systemctl daemon-reload && systemctl restart $(SERVICE_NAME) && journalctl -u $(SERVICE_NAME) -f"
