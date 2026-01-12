local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker3/build',
  grpcServers: [{
    listenPaths: ['worker3/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
