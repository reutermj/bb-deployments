local common = import 'common.libsonnet';

{
  blobstore: common.blobstore,
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  scheduler: { address: 'localhost:9203' },
  buildDirectories: [
    {
      native: {
        buildDirectoryPath: std.extVar('PWD') + '/worker8/build',
        cacheDirectoryPath: 'worker8/cache',
        maximumCacheFileCount: 10000,
        maximumCacheSizeBytes: 1024 * 1024 * 1024,
        cacheReplacementPolicy: 'LEAST_RECENTLY_USED',
      },
      runners: [{
        endpoint: { address: 'unix:worker8/runner' },
        concurrency: 1,
        maximumFilePoolFileCount: 10000,
        maximumFilePoolSizeBytes: 1024 * 1024 * 1024,
        platform: {},
        workerId: {
          datacenter: 'paris',
          rack: '1',
          slot: '8',
          hostname: 'worker8.example.com',
        },
      }],
    },
  ],
  filePool: {
    blockDevice: {
      file: {
        path: 'worker8/filepool',
        sizeBytes: 1024 * 1024 * 1024,
      },
    },
  },
  inputDownloadConcurrency: 10,
  outputUploadConcurrency: 11,
  directoryCache: {
    maximumCount: 1000,
    maximumSizeBytes: 1000 * 1024,
    cacheReplacementPolicy: 'LEAST_RECENTLY_USED',
  },
}
