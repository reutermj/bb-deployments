local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker5/build',
  grpcServers: [{
    listenPaths: ['worker5/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
