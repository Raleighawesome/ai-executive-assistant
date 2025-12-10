# AI Executive Assistant - n8n Templates

This directory contains templates for automating your AI Executive Assistant workflows using n8n and Docker.

## Contents

1. **docker-compose.yml** - Docker services for n8n and Qdrant
2. **n8n-meeting-processor.json** - Workflow for automatic meeting processing
3. **n8n-daily-briefing.json** - Workflow for daily briefing generation
4. **README.md** - This file

## Quick Start

### 1. Set Up Docker Services

**Step 1: Customize paths**

Edit `docker-compose.yml` and replace these environment variables:

```yaml
- VAULT_PATH=/path/to/your/obsidian/vault
- SCRIPTS_PATH=/path/to/ai-executive-assistant/scripts
```

Or set them in your shell before running docker-compose:

```bash
export VAULT_PATH="/Users/yourname/Documents/MyVault"
export SCRIPTS_PATH="/Users/yourname/ai-executive-assistant/scripts"
```

**Step 2: Start services**

```bash
# Start n8n and Qdrant
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f
```

**Step 3: Access n8n**

Open http://localhost:5678 in your browser.

Default credentials (CHANGE THESE!):
- Username: `admin`
- Password: `changeme`

**Step 4: Change default password**

Edit `docker-compose.yml`:

```yaml
- N8N_BASIC_AUTH_USER=your_username
- N8N_BASIC_AUTH_PASSWORD=your_secure_password
```

Then restart:

```bash
docker-compose restart n8n
```

### 2. Import n8n Workflows

**Meeting Processor Workflow:**

1. In n8n, go to **Workflows** → **Add Workflow**
2. Click the **⋮** menu → **Import from File**
3. Select `n8n-meeting-processor.json`
4. Customize the workflow (see below)
5. Click **Save** and **Activate**

**Daily Briefing Workflow:**

1. In n8n, go to **Workflows** → **Add Workflow**
2. Click the **⋮** menu → **Import from File**
3. Select `n8n-daily-briefing.json`
4. Customize the workflow (see below)
5. Click **Save** and **Activate**

## Customizing the Workflows

Both workflows use placeholder paths that you must replace with your actual paths.

### Meeting Processor Customization

**Node: Watch Meetings Folder**
- Replace `{{VAULT_PATH}}` with your vault path
- Example: `/Users/yourname/Documents/MyVault`

**Node: Process 1:1 Meeting**
- Update command: `cd /Users/yourname/Documents/MyVault && python scripts/process_one-on-one_notes.py "={{ $json.relativeFilePath }}"`
- Add environment variables if needed:
  ```yaml
  environment:
    GOOGLE_CLOUD_PROJECT: your-project-id
    GOOGLE_IMPERSONATE_SERVICE_ACCOUNT: your-sa@project.iam.gserviceaccount.com
  ```

**Node: Process Group Meeting**
- Update command: `cd /Users/yourname/Documents/MyVault && python scripts/process_mtg_notes.py "={{ $json.relativeFilePath }}"`
- Add same environment variables as above

### Daily Briefing Customization

**Node: Schedule Daily**
- Default: 6 AM weekdays
- Change cron expression for different schedule:
  - `0 7 * * 1-5` = 7 AM weekdays
  - `30 6 * * *` = 6:30 AM daily
  - `0 8 * * 1,3,5` = 8 AM Mon/Wed/Fri

**Node: Fetch Calendar Events**
- Replace `{{SCRIPTS_PATH}}` with your scripts directory
- Example: `/Users/yourname/ai-executive-assistant/scripts`
- Ensure Google Calendar credentials are configured

**Node: Parse Calendar Data**
- Customize email domain filter:
  ```javascript
  return attendees.some(email =>
    email.includes('@yourcompany.com') ||
    email.includes('@yourworkdomain.com')
  );
  ```
- Or remove filter to include all events:
  ```javascript
  const workEvents = events; // No filtering
  ```

**Node: Generate Daily Briefing**
- Replace `{{VAULT_PATH}}` with your vault path
- Add required environment variables:
  ```yaml
  environment:
    GOOGLE_CLOUD_PROJECT: your-project-id
    GOOGLE_IMPERSONATE_SERVICE_ACCOUNT: your-sa@project.iam.gserviceaccount.com
    QDRANT_URL: http://qdrant:6333
  ```

## Environment Variables Reference

### Required for Vertex AI (Google Gemini)

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="your-sa@project.iam.gserviceaccount.com"
export CLOUDSDK_ACTIVE_CONFIG_NAME="default"
```

### Required for OpenAI

```bash
export OPENAI_API_KEY="sk-..."
```

### Required for Anthropic Claude

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Optional for Qdrant

```bash
export QDRANT_URL="http://localhost:6333"
export QDRANT_COLLECTION="personal_assistant"
```

### Calendar Integration

```bash
# Path to Google Calendar OAuth token
export GOOGLE_OAUTH_TOKEN="/path/to/gmail_oauth_token.json"
```

## Testing the Workflows

### Test Meeting Processor

1. Create a test meeting note in your vault:
   ```bash
   echo "---
date: 2025-12-09
---

# Test Meeting

## Transcript

This is a test meeting note." > /path/to/vault/Meetings/12-09-25\ -\ Test\ Meeting.md
   ```

2. Watch n8n execution logs
3. Verify the meeting was processed:
   - Check for updated frontmatter
   - Look for generated summary
   - Confirm action items extracted

### Test Daily Briefing

1. Manually trigger the workflow:
   - In n8n, open the Daily Briefing workflow
   - Click **Execute Workflow** (manually)

2. Or test with sample calendar data:
   - Edit the **Parse Calendar Data** node
   - Add test events:
     ```json
     {
       "events": [
         {
           "date": "2025-12-09",
           "start_time": "10:00:00",
           "end_time": "10:30:00",
           "title": "Team Sync",
           "accepted_attendees": ["you@company.com"]
         }
       ]
     }
     ```

3. Verify briefing was created:
   ```bash
   cat /path/to/vault/Dashboard/Daily\ Briefing.md
   ```

## Troubleshooting

### n8n Can't Access Files

**Issue**: Workflow fails with "Permission denied" or "File not found"

**Solutions**:
1. Check volume mounts in `docker-compose.yml`:
   ```yaml
   volumes:
     - /full/path/to/vault:/vault:ro
   ```
2. Ensure paths in workflows match mounted paths
3. Verify file permissions: `chmod -R 755 /path/to/vault`

### Python Scripts Fail

**Issue**: Execute Command nodes fail with "ModuleNotFoundError"

**Solutions**:
1. Install Python dependencies in the container:
   ```bash
   docker exec -it ai-assistant-n8n /bin/bash
   pip install google-cloud-aiplatform vertexai
   ```
2. Or mount a virtualenv:
   ```yaml
   volumes:
     - /path/to/.venv:/app/.venv:ro
   ```
3. Update commands to use correct Python:
   ```bash
   /app/.venv/bin/python scripts/process_mtg_notes.py
   ```

### Calendar Fetch Fails

**Issue**: "Failed to fetch calendar events"

**Solutions**:
1. Verify OAuth token exists and is valid
2. Check Google Calendar API is enabled
3. Ensure credentials.json has correct permissions
4. Test calendar script manually:
   ```bash
   cd scripts/calendar-events
   python fetch_today_events.py
   ```

### Qdrant Connection Fails

**Issue**: "Failed to connect to Qdrant"

**Solutions**:
1. Check Qdrant is running: `docker-compose ps qdrant`
2. Verify network connectivity: `docker exec ai-assistant-n8n curl http://qdrant:6333/healthz`
3. Check collection exists: `curl http://localhost:6333/collections`
4. Run embedding script to create collection:
   ```bash
   python scripts/embed_to_qdrant.py
   ```

### High Memory Usage

**Issue**: Docker containers consuming too much memory

**Solutions**:
1. Limit container memory in `docker-compose.yml`:
   ```yaml
   services:
     n8n:
       mem_limit: 1g
       mem_reservation: 512m
   ```
2. Reduce n8n execution retention:
   ```yaml
   environment:
     - EXECUTIONS_DATA_SAVE_ON_SUCCESS=none
     - EXECUTIONS_DATA_SAVE_ON_ERROR=all
   ```
3. Configure Qdrant memory limits:
   ```yaml
   services:
     qdrant:
       mem_limit: 2g
   ```

## Advanced Customizations

### Add Notifications

**Email Notification** (connect to success/error nodes):

1. Add **Send Email** node
2. Configure SMTP settings
3. Connect to "Log Success" or "Handle Error" nodes
4. Message template:
   ```
   Daily briefing ready!

   Events: {{ $json.eventCount }}
   File: {{ $json.briefingFile }}
   ```

**Slack Notification**:

1. Add **Slack** node
2. Connect to success nodes
3. Message:
   ```
   ✅ Daily briefing created

   📅 Events processed: {{ $json.eventCount }}
   📄 Briefing: Dashboard/Daily Briefing.md
   ```

### Custom Meeting Types

Add support for custom meeting types:

1. Edit **Detect Meeting Type** node
2. Add new patterns:
   ```javascript
   const isStandUp = filename.match(/stand-?up/i);
   const isRetrospective = filename.match(/retro/i);
   ```
3. Add new routes in **Switch** node
4. Create new processing nodes

### Batch Processing

Process multiple files at once:

1. Change trigger to **Cron** (e.g., nightly)
2. Replace file watcher with **Execute Command**:
   ```bash
   find /vault/Meetings -name "*.md" -mtime -1
   ```
3. Add **Split In Batches** node
4. Process each file through existing workflow

## Docker Commands Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart a service
docker-compose restart n8n

# View logs
docker-compose logs -f n8n
docker-compose logs -f qdrant

# Enter container shell
docker exec -it ai-assistant-n8n /bin/bash

# Check service status
docker-compose ps

# Remove all data (WARNING: deletes volumes)
docker-compose down -v

# Update images
docker-compose pull
docker-compose up -d
```

## Security Considerations

1. **Change default passwords** in `docker-compose.yml`
2. **Restrict network access** - Consider using firewall rules:
   ```bash
   # Only allow local connections
   iptables -A INPUT -p tcp --dport 5678 -s 127.0.0.1 -j ACCEPT
   iptables -A INPUT -p tcp --dport 5678 -j DROP
   ```
3. **Use HTTPS** for production:
   - Set up reverse proxy (nginx, Caddy)
   - Configure SSL certificates
   - Update `N8N_PROTOCOL=https`
4. **Limit file access**:
   - Use `:ro` (read-only) mounts where possible
   - Run containers as non-root user
5. **Secure API keys**:
   - Use Docker secrets for production
   - Never commit keys to version control
   - Rotate credentials regularly

## Migration from Existing Setup

If you're already running these scripts manually:

1. **Back up your data**:
   ```bash
   tar -czf vault-backup.tar.gz /path/to/vault
   ```

2. **Test workflows with read-only mounts**:
   ```yaml
   volumes:
     - /path/to/vault:/vault:ro  # Read-only
   ```

3. **Verify output** before switching to read-write

4. **Gradually migrate**:
   - Start with daily briefing (lowest risk)
   - Then add meeting processor
   - Finally automate calendar integration

## Support

- **n8n Documentation**: https://docs.n8n.io
- **Qdrant Documentation**: https://qdrant.tech/documentation
- **Docker Compose Reference**: https://docs.docker.com/compose

## License

MIT License - See main project LICENSE file
