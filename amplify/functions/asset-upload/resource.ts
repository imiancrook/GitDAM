import { defineFunction } from '@aws-amplify/backend';

export const assetUpload = defineFunction({
  name: 'asset-upload',
  entry: './handler.ts',
});
