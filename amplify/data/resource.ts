import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  Repository: a
    .model({
      name: a.string().required(),
      description: a.string(),
      defaultBranch: a.string().default('main'),
      lfsEnabled: a.boolean().default(true),
      assets: a.hasMany('Asset', 'repositoryId'),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
    })
    .authorization([
      a.allow.owner(),
      a.allow.authenticated().to(['read']),
    ]),

  Asset: a
    .model({
      repositoryId: a.id().required(),
      repository: a.belongsTo('Repository', 'repositoryId'),
      fileName: a.string().required(),
      filePath: a.string().required(),
      fileSize: a.integer().required(),
      fileType: a.string(),
      mimeType: a.string(),
      branch: a.string().default('main'),
      commitSha: a.string(),
      lfsOid: a.string(),
      lfsPointer: a.json(),
      isLFS: a.boolean().default(false),
      versions: a.hasMany('AssetVersion', 'assetId'),
      metadata: a.json(),
      tags: a.string().array(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
    })
    .authorization([
      a.allow.owner(),
      a.allow.authenticated().to(['read']),
    ]),

  AssetVersion: a
    .model({
      assetId: a.id().required(),
      asset: a.belongsTo('Asset', 'assetId'),
      versionNumber: a.integer().required(),
      commitSha: a.string().required(),
      lfsOid: a.string(),
      fileSize: a.integer().required(),
      storageKey: a.string(),
      changeDescription: a.string(),
      changedBy: a.string(),
      createdAt: a.datetime(),
    })
    .authorization([
      a.allow.owner(),
      a.allow.authenticated().to(['read']),
    ]),

  LFSObject: a
    .model({
      oid: a.string().required(),
      size: a.integer().required(),
      storageKey: a.string().required(),
      storageUrl: a.string(),
      repositoryId: a.id(),
      uploadedBy: a.string(),
      verified: a.boolean().default(false),
      expiresAt: a.datetime(),
      createdAt: a.datetime(),
    })
    .authorization([
      a.allow.owner(),
      a.allow.authenticated().to(['read']),
    ]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
    apiKeyAuthorizationMode: {
      expiresInDays: 30,
    },
  },
});
