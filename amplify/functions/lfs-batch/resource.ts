import { defineFunction } from '@aws-amplify/backend';

export const lfsBatch = defineFunction({
  name: 'lfs-batch',
  entry: './handler.ts',
});
