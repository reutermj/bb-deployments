local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker2/build',
  grpcServers: [{
    listenPaths: ['worker2/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
