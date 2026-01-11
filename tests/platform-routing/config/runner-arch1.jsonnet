local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker-arch1/build',
  grpcServers: [{
    listenPaths: ['worker-arch1/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
