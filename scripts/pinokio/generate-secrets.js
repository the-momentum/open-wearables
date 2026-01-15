/**
 * Generate secure secrets for Open Wearables local installation
 * This script is called during Pinokio installation to create unique secrets.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// Generate a secure random string (similar to Python's secrets.token_urlsafe)
function generateSecretKey(length = 64) {
  return crypto.randomBytes(length).toString('base64url');
}

// Path to the .env file
const envPath = path.join(__dirname, '..', '..', 'backend', 'config', '.env');

// Check if .env exists
if (!fs.existsSync(envPath)) {
  console.error('❌ Error: .env file not found at', envPath);
  console.error('   Please run the install script first to copy the template.');
  process.exit(1);
}

// Read the current .env file
let envContent = fs.readFileSync(envPath, 'utf8');

// Check if SECRET_KEY is placeholder
if (envContent.includes('SECRET_KEY=PLACEHOLDER_WILL_BE_GENERATED')) {
  // Generate new secret key
  const newSecretKey = generateSecretKey();
  
  // Replace placeholder with generated key
  envContent = envContent.replace(
    'SECRET_KEY=PLACEHOLDER_WILL_BE_GENERATED',
    `SECRET_KEY=${newSecretKey}`
  );
  
  // Write back to file
  fs.writeFileSync(envPath, envContent);
  
  console.log('✅ Generated new SECRET_KEY');
} else if (envContent.includes('SECRET_KEY=')) {
  console.log('ℹ️  SECRET_KEY already configured, skipping generation');
} else {
  // SECRET_KEY line doesn't exist, append it
  const newSecretKey = generateSecretKey();
  envContent += `\n# Auto-generated secret key\nSECRET_KEY=${newSecretKey}\n`;
  fs.writeFileSync(envPath, envContent);
  console.log('✅ Added new SECRET_KEY');
}

console.log('🔐 Secrets configuration complete!');

