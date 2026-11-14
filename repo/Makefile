.PHONY: install test bench demo frames live room camera
install:
	pip install -r requirements.txt
test:
	python -m pytest -q
bench:
	python -m oracolo.bench --runs 30
demo:
	PYTHONPATH=. python scripts/run_demo.py
frames:
	PYTHONPATH=. python scripts/render_scene.py out/demo.mp4
live:
	PYTHONPATH=. python scripts/run_live.py --loop
room:
	python scripts/make_room_dxf.py scenarios/stanza_esempio.json scenarios/stanza.dxf
camera:
	PYTHONPATH=. python scripts/run_camera.py
