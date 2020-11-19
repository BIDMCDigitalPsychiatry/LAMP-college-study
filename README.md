# College Study Script

The app code is in `main.py`, and the script relies on our team's Docker infrastructure. If you make a change to the imports at the top of the file, update the `requirements.txt` file, and then run `./update.sh` to update the live version that can be found at `https://college-study.lamp.digital/`. Or, manually run `sudo docker build -t college_study .` and then update the docker service. The sample environment variables required can be found in `env.sample`.
