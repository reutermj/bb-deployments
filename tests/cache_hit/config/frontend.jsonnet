local common = import 'common.libsonnet';

{
  grpcServers: [{
    listenAddresses: [':9020'],
    authenticationPolicy: { allow: {} },
  }],
  schedulers: {
    '': {
      endpoint: {
        address: 'localhost:9022',
        addMetadataJmespathExpression: {
          expression: |||
            {
              "build.bazel.remote.execution.v2.requestmetadata-bin": incomingGRPCMetadata."build.bazel.remote.execution.v2.requestmetadata-bin"
            }
          |||,
        },
      },
    },
  },
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  contentAddressableStorage: {
    backend: common.blobstore.contentAddressableStorage,
    getAuthorizer: { allow: {} },
    putAuthorizer: { allow: {} },
    findMissingAuthorizer: { allow: {} },
  },
  actionCache: {
    backend: common.blobstore.actionCache,
    getAuthorizer: { allow: {} },
    putAuthorizer: { allow: {} },
  },
  executeAuthorizer: { allow: {} },
}
