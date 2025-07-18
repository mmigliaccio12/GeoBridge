# Railway Deployment Guide for CustomSat

This guide will help you deploy your CustomSat Insurance Risk Analysis Platform to Railway.

## Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Repository**: Your code should be in a GitHub repository
3. **Sentinel Hub Account**: You'll need API credentials for satellite data

## Environment Variables Required

Before deploying, you'll need to set these environment variables in Railway:

### Required Variables:
- `SECRET_KEY`: A secure secret key for Flask sessions (generate a strong random string)
- `SH_CLIENT_ID`: Your Sentinel Hub client ID
- `SH_CLIENT_SECRET`: Your Sentinel Hub client secret

### Optional Variables:
- `FLASK_ENV`: Set to `production` (default) or `development` for debug mode
- `GUNICORN_WORKERS`: Number of worker processes (default: 2)

## Deployment Methods

### Method 1: Web Interface (Recommended)

1. **Connect Repository**:
   - Go to [railway.app](https://railway.app) and sign in
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository and the `sentinel-app-v2` folder

2. **Set Environment Variables**:
   - In your Railway project dashboard
   - Go to "Variables" tab
   - Add all required environment variables listed above

3. **Deploy**:
   - Railway will automatically detect your Python app
   - It will use the `Procfile` to start your app with Gunicorn
   - Deployment usually takes 3-5 minutes

### Method 2: Railway CLI

1. **Install Railway CLI**:
   ```bash
   npm install -g @railway/cli
   ```

2. **Login and Initialize**:
   ```bash
   railway login
   cd sentinel-app-v2
   railway init
   ```

3. **Set Environment Variables**:
   ```bash
   railway variables set SECRET_KEY="your-secret-key-here"
   railway variables set SH_CLIENT_ID="your-client-id"
   railway variables set SH_CLIENT_SECRET="your-client-secret"
   # Add other variables as needed
   ```

4. **Deploy**:
   ```bash
   railway up
   ```

## Post-Deployment Steps

1. **Test Your Application**:
   - Railway will provide a URL (e.g., `https://your-app.railway.app`)
   - Test the login functionality with `admin@customsat.it` / `password`

2. **Custom Domain** (Optional):
   - In Railway dashboard, go to "Settings" > "Domains"
   - Add your custom domain

3. **Monitor Logs**:
   - Check deployment logs in Railway dashboard
   - Monitor application performance

## Troubleshooting

### Common Issues:

1. **Build Failures**:
   - Check that all dependencies in `requirements.txt` are available
   - Ensure Python version compatibility

2. **Runtime Errors**:
   - Check Railway logs for specific error messages
   - Verify all environment variables are set correctly

3. **Sentinel Hub API Issues**:
   - Verify your API credentials are correct
   - Check API quotas and limits

4. **Memory/Performance Issues**:
   - Adjust `GUNICORN_WORKERS` environment variable
   - Consider upgrading Railway plan for more resources

## Production Considerations

1. **Security**:
   - Use a strong, unique `SECRET_KEY`
   - Keep API credentials secure
   - Consider implementing rate limiting

2. **Performance**:
   - Monitor response times and adjust worker count
   - Consider caching for frequently accessed data
   - Optimize satellite data processing

3. **Monitoring**:
   - Set up health checks
   - Monitor application logs
   - Track API usage

## Support

- Railway Documentation: [docs.railway.app](https://docs.railway.app)
- Sentinel Hub Documentation: [docs.sentinel-hub.com](https://docs.sentinel-hub.com)

Your app is now configured for Railway deployment with production-ready settings including:
- Gunicorn WSGI server for better performance
- Proper port configuration
- Environment-based configuration
- Health checks and restart policies 