local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker1/build',
  grpcServers: [{
    listenPaths: ['worker1/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
