local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker8/build',
  grpcServers: [{
    listenPaths: ['worker8/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
