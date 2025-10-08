#!/usr/bin/env python3
"""
MedAssistant AI Service Setup Script

This script helps configure the OpenAI API integration for the MedAssistant application.
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create a .env file with OpenAI configuration template."""
    env_content = """# MedAssistant Environment Configuration

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=1
HOST=127.0.0.1
PORT=5000

# OpenAI Configuration
# IMPORTANT: Replace with your actual OpenAI API key
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# AI Service Configuration
# Set to 1 to force stub mode (useful for testing without API calls)
AI_STUB=0
# Localise fallback safety hints when OpenAI is unreachable (optional)
# AI_FALLBACK_LANGUAGE=de
# AI_FALLBACK_PREFIX=MedAssistant-Notfallantwort:
# AI_FALLBACK_LINES=Diese Hinweise ersetzen keine ärztliche Beratung.|Rufen Sie bei starken Beschwerden den Notruf.

# Database Configuration
SQLALCHEMY_DATABASE_URI=sqlite:///instance/health_app.db

# JWT Configuration
JWT_SECRET_KEY=your_jwt_secret_key_here_change_in_production

# Security Configuration
SECRET_KEY=your_secret_key_here_change_in_production
"""
    
    env_path = Path(".env")
    if env_path.exists():
        print("⚠️  .env file already exists. Backing up to .env.backup")
        env_path.rename(".env.backup")
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("✅ Created .env file with OpenAI configuration template")
    return True

def check_openai_key():
    """Check if OpenAI API key is configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and api_key != "your_openai_api_key_here":
        print("✅ OpenAI API key is configured")
        return True
    else:
        print("❌ OpenAI API key is not configured")
        return False

def test_ai_service():
    """Test the AI service integration."""
    try:
        from health_app.services.ai_service import chat_json, is_stub_mode
        
        print(f"🔍 AI Service Status: {'Stub Mode' if is_stub_mode() else 'Live Mode'}")
        
        # Test with a simple health query
        test_prompt = "Patient reports headache and fever for 2 days. No allergies. Age 30, male."
        
        try:
            result = chat_json(test_prompt)
            print("✅ AI Service test successful")
            print(f"📋 Sample response: {result.get('risk_evaluation', {}).get('risk_level', 'unknown')} risk")
            return True
        except Exception as e:
            print(f"❌ AI Service test failed: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import AI service: {e}")
        return False

def main():
    """Main setup function."""
    print("🚀 MedAssistant AI Service Setup")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("health_app").exists():
        print("❌ Please run this script from the MedAssistant project root directory")
        sys.exit(1)
    
    # Create .env file if it doesn't exist
    if not Path(".env").exists():
        create_env_file()
        print("\n📝 Next steps:")
        print("1. Get your OpenAI API key from: https://platform.openai.com/api-keys")
        print("2. Edit the .env file and replace 'your_openai_api_key_here' with your actual API key")
        print("3. Run this script again to test the integration")
        return
    
    # Check API key configuration
    if not check_openai_key():
        print("\n📝 To configure your OpenAI API key:")
        print("1. Get your API key from: https://platform.openai.com/api-keys")
        print("2. Edit the .env file and replace 'your_openai_api_key_here' with your actual API key")
        print("3. Restart the application")
        return
    
    # Test AI service
    print("\n🧪 Testing AI Service Integration...")
    if test_ai_service():
        print("\n🎉 AI Service is ready!")
        print("The MedAssistant application can now use real AI-powered health analysis.")
    else:
        print("\n⚠️  AI Service test failed. Check your API key and try again.")

if __name__ == "__main__":
    main()
