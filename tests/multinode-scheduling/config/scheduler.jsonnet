local common = import 'common.libsonnet';

{
  adminHttpServers: [{
    listenAddresses: [':9114'],
    authenticationPolicy: { allow: {} },
  }],
  clientGrpcServers: [{
    listenAddresses: [':9112'],
    authenticationPolicy: { allow: {} },
  }],
  workerGrpcServers: [{
    listenAddresses: [':9113'],
    authenticationPolicy: { allow: {} },
  }],
  contentAddressableStorage: common.blobstore.contentAddressableStorage,
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  executeAuthorizer: { allow: {} },
  modifyDrainsAuthorizer: { allow: {} },
  killOperationsAuthorizer: { allow: {} },
  synchronizeAuthorizer: { allow: {} },
  platformQueueWithNoWorkersTimeout: '900s',
  // Use actionAndCommand platform key extractor to allow multinode tasks
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
