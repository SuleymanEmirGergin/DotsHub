# Run Emulator Setup Script

Write-Host "Starting Backend..."
cd backend
python -m pip install -r requirements.txt
python -m pip install uvicorn fastapi supabase pydantic python-dotenv

Start-Process -FilePath "cmd.exe" -ArgumentList "/k python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -WindowStyle Normal

Write-Host "Backend started in new window."
Write-Host "Now starting Expo..."

cd ../mobile
npm install
Start-Process -FilePath "cmd.exe" -ArgumentList "/k npx expo start" -WindowStyle Normal

Write-Host "Done! Expo QR code should appear in the new window."
Write-Host "Check the new windows for status."
