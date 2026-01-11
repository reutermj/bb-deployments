{
  blobstore: {
    contentAddressableStorage: {
      grpc: {
        address: 'localhost:9111',
      },
    },
    actionCache: {
      completenessChecking: {
        backend: {
          grpc: {
            address: 'localhost:9111',
          },
        },
        maximumTotalTreeSizeBytes: 64 * 1024 * 1024,
      },
    },
  },
  maximumMessageSizeBytes: 2 * 1024 * 1024,
}
