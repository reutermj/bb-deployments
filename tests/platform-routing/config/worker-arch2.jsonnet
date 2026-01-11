local common = import 'common.libsonnet';

{
  blobstore: common.blobstore,
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  scheduler: { address: 'localhost:9063' },
  buildDirectories: [
    {
      native: {
        buildDirectoryPath: std.extVar('PWD') + '/worker-arch2/build',
        cacheDirectoryPath: 'worker-arch2/cache',
        maximumCacheFileCount: 10000,
        maximumCacheSizeBytes: 1024 * 1024 * 1024,
        cacheReplacementPolicy: 'LEAST_RECENTLY_USED',
      },
      runners: [{
        endpoint: { address: 'unix:worker-arch2/runner' },
        concurrency: 1,
        maximumFilePoolFileCount: 10000,
        maximumFilePoolSizeBytes: 1024 * 1024 * 1024,
        platform: {
          properties: [
            { name: 'arch', value: 'arch2' },
          ],
        },
        workerId: {
          datacenter: 'paris',
          rack: '4',
          slot: '2',
          hostname: 'worker-arch2.example.com',
        },
      }],
    },
  ],
  filePool: {
    blockDevice: {
      file: {
        path: 'worker-arch2/filepool',
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
