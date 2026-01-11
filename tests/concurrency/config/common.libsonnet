{
  blobstore: {
    contentAddressableStorage: {
      grpc: {
        address: 'localhost:9091',
      },
    },
    actionCache: {
      completenessChecking: {
        backend: {
          grpc: {
            address: 'localhost:9091',
          },
        },
        maximumTotalTreeSizeBytes: 64 * 1024 * 1024,
      },
    },
  },
  maximumMessageSizeBytes: 2 * 1024 * 1024,
}
