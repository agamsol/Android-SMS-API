:: Build from repo root, using backend/Dockerfile
cd /d %~dp0..
docker build --no-cache -f backend/Dockerfile -t android-sms-api:0.5 -t android-sms-api:latest .
