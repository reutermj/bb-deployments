local common = import 'common.libsonnet';

{
  adminHttpServers: [{
    listenAddresses: [':9124'],
    authenticationPolicy: { allow: {} },
  }],
  clientGrpcServers: [{
    listenAddresses: [':9122'],
    authenticationPolicy: { allow: {} },
  }],
  workerGrpcServers: [{
    listenAddresses: [':9123'],
    authenticationPolicy: { allow: {} },
  }],
  contentAddressableStorage: common.blobstore.contentAddressableStorage,
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  executeAuthorizer: { allow: {} },
  modifyDrainsAuthorizer: { allow: {} },
  killOperationsAuthorizer: { allow: {} },
  synchronizeAuthorizer: { allow: {} },
  platformQueueWithNoWorkersTimeout: '900s',
  actionRouter: {
    simple: {
      platformKeyExtractor: { actionAndCommand: {} },
      invocationKeyExtractors: [
        { toolInvocationId: {} },
        { correlatedInvocationsId: {} },
      ],
      initialSizeClassAnalyzer: {
        defaultExecutionTimeout: '1800s',
        maximumExecutionTimeout: '7200s',
      },
    },
  },
}
