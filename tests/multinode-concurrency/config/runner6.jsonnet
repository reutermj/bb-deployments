local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker6/build',
  grpcServers: [{
    listenPaths: ['worker6/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
