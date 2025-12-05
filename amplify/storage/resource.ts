import { defineStorage } from '@aws-amplify/backend';

export const storage = defineStorage({
  name: 'gitdamStorage',
  access: (allow) => ({
    'lfs-objects/*': [
      allow.authenticated.to(['read', 'write', 'delete']),
    ],
    'repositories/{repository_id}/*': [
      allow.authenticated.to(['read', 'write']),
    ],
    'assets/{asset_id}/*': [
      allow.authenticated.to(['read', 'write', 'delete']),
    ],
  }),
});
