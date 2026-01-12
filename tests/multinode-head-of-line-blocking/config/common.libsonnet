{
  blobstore: {
    contentAddressableStorage: {
      grpc: {
        address: 'localhost:9121',
      },
    },
    actionCache: {
      completenessChecking: {
        backend: {
          grpc: {
            address: 'localhost:9121',
          },
        },
        maximumTotalTreeSizeBytes: 64 * 1024 * 1024,
      },
    },
  },
  maximumMessageSizeBytes: 2 * 1024 * 1024,
}
