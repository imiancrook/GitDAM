import { defineFunction } from '@aws-amplify/backend';

export const assetDownload = defineFunction({
  name: 'asset-download',
  entry: './handler.ts',
});
