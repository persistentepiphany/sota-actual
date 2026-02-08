import { firestoreDb } from '../src/lib/firestore';
import { collections } from '../src/lib/firestore';

async function removeDuplicateAgents() {
  try {
    console.log('🔍 Searching for duplicate agents...');
    
    // Get all agents
    const agents = await firestoreDb.agent.findMany({
      orderBy: { id: 'asc' }
    });

    console.log(`📊 Total agents: ${agents.length}`);

    // Group by title (case-insensitive)
    const agentsByTitle = new Map<string, typeof agents>();
    
    for (const agent of agents) {
      const normalizedTitle = agent.title.toLowerCase().trim();
      if (!agentsByTitle.has(normalizedTitle)) {
        agentsByTitle.set(normalizedTitle, []);
      }
      agentsByTitle.get(normalizedTitle)!.push(agent);
    }

    // Find duplicates
    const duplicates: number[] = [];
    
    for (const [title, agentGroup] of agentsByTitle) {
      if (agentGroup.length > 1) {
        console.log(`\n🔄 Found ${agentGroup.length} agents with title "${title}":`);
        
        // Sort by id (keep the first one, delete the rest)
        agentGroup.sort((a, b) => a.id - b.id);
        
        for (let i = 0; i < agentGroup.length; i++) {
          const agent = agentGroup[i];
          if (i === 0) {
            console.log(`  ✅ KEEP: ID ${agent.id} (created: ${agent.createdAt})`);
          } else {
            console.log(`  ❌ DELETE: ID ${agent.id} (created: ${agent.createdAt})`);
            duplicates.push(agent.id);
          }
        }
      }
    }

    if (duplicates.length === 0) {
      console.log('\n✨ No duplicates found!');
      return;
    }

    console.log(`\n🗑️  Deleting ${duplicates.length} duplicate agents...`);
    
    // Delete related records first
    console.log('  - Deleting related orders...');
    let deletedOrders = 0;
    for (const agentId of duplicates) {
      const orderSnaps = await collections.orders.where('agentId', '==', agentId).get();
      for (const doc of orderSnaps.docs) {
        await doc.ref.delete();
        deletedOrders++;
      }
    }
    console.log(`    Deleted ${deletedOrders} orders`);

    console.log('  - Deleting related API keys...');
    let deletedKeys = 0;
    for (const agentId of duplicates) {
      const keySnaps = await collections.agentApiKeys.where('agentId', '==', agentId).get();
      for (const doc of keySnaps.docs) {
        await doc.ref.delete();
        deletedKeys++;
      }
    }
    console.log(`    Deleted ${deletedKeys} API keys`);

    // Now delete the duplicate agents
    console.log('  - Deleting duplicate agents...');
    let deletedCount = 0;
    for (const agentId of duplicates) {
      const agentSnaps = await collections.agents.where('id', '==', agentId).get();
      for (const doc of agentSnaps.docs) {
        await doc.ref.delete();
        deletedCount++;
      }
    }

    console.log(`\n✅ Successfully deleted ${deletedCount} duplicate agents!`);
    
    // Show final count
    const finalAgents = await firestoreDb.agent.findMany({});
    console.log(`📊 Final agent count: ${finalAgents.length}`);

  } catch (error) {
    console.error('❌ Error removing duplicates:', error);
    throw error;
  }
}

removeDuplicateAgents()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
