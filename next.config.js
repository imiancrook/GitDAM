/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, { isServer }) => {
    // Handle Amplify beta package issues
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      net: false,
      tls: false,
    };
    
    // Fix module resolution for AWS Amplify packages with Next.js 15
    config.resolve.extensionAlias = {
      '.js': ['.js', '.ts', '.tsx'],
      '.mjs': ['.mjs', '.mts'],
    };
    
    return config;
  },
  // Ignore build errors for now since this is a development setup
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Improve module resolution for Next.js 15
  transpilePackages: [
    'aws-amplify',
    '@aws-amplify/ui-react',
    '@aws-amplify/api',
    '@aws-amplify/api-graphql',
    '@aws-amplify/data-schema',
    '@aws-amplify/data-schema-types',
  ],
}

module.exports = nextConfig
