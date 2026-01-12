local common = import 'common.libsonnet';

{
  adminHttpServers: [{
    listenAddresses: [':9204'],
    authenticationPolicy: { allow: {} },
  }],
  clientGrpcServers: [{
    listenAddresses: [':9202'],
    authenticationPolicy: { allow: {} },
  }],
  workerGrpcServers: [{
    listenAddresses: [':9203'],
    authenticationPolicy: { allow: {} },
  }],
  contentAddressableStorage: common.blobstore.contentAddressableStorage,
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  executeAuthorizer: { allow: {} },
  modifyDrainsAuthorizer: { allow: {} },
  killOperationsAuthorizer: { allow: {} },
  synchronizeAuthorizer: { allow: {} },
  platformQueueWithNoWorkersTimeout: '900s',
  // Disable action router to allow multinode tasks to be scheduled
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
